#!/usr/bin/env python3
import io
import math
import numpy as np
from PIL import Image, ImageDraw


def encode_number(n):
    neg, n = n < 0, abs(n)
    w = 1 + (1 if n == 0 else math.ceil(math.sqrt(1 + int(math.log2((n))))))
    h = w + neg
    g = np.zeros((h, w), dtype=np.uint8)
    g[h-1, 0] = neg
    for i in range(1, w):
        g[0, i] = 1
        g[i, 0] = 1
    mask = 1
    for y in range(1, w):
        for x in range(1, w):
            g[y, x] = 1 if (n & mask) else 0
            mask <<= 1
    return g


class Decoder:
    symbols = dict()
    symbols[(2, 0)] = '$'
    symbols[(3, 2)] = 'True'
    symbols[(3, 8)] = 'False'
    symbols[(3, 12)] = '='
    symbols[(4, 40)] = 'div'
    symbols[(4, 146)] = 'mul'
    symbols[(4, 365)] = 'add'
    symbols[(4, 401)] = 'dec'
    symbols[(4, 416)] = 'lt'
    symbols[(4, 417)] = 'inc'
    symbols[(4, 448)] = 'eq'

    def _extract_border(self, px, x, y, w, h):
        if ((x < 0) or (y < 0) or (w <= 0) or (h <= 0)
            or (y + h >= px.shape[0])
            or (x + w >= px.shape[1])):
            return

        res = np.zeros(((w + h - 2) * 2, ), dtype=px.dtype)
        i = 0
        for dx in range(x, x + w):
            res[i] = px[y, dx]
            i += 1
        for dy in range(y + 1, y + h):
            res[i] = px[dy, x + w - 1]
            i += 1
        for dx in reversed(range(x, x + w - 1)):
            res[i] = px[y + h - 1, dx]
            i += 1
        for dy in reversed(range(y + 1, y + h - 1)):
            res[i] = px[dy, x]
            i += 1
        return res

    def _unpack_number(self, px, x, y, w, h):
        n = 0
        bit = 1
        for dy in range(1, h):
            for dx in range(1, w):
                n |= bit if px[y + dy, x + dx] else 0
                bit <<= 1
        return n

    def decode_symbol(self, px, x, y):
        w = 1
        while (y + w < px.shape[0]) and (x + w < px.shape[1]) and px[y, x + w] and px[y + w, x]:
            w += 1
        else:
            neg = (y + w < px.shape[0]) and (px[y + w, x] != 0)

        if w < 2: return
        border = self._extract_border(px, x=x-1, y=y-1, w=w+2, h=w+2+neg)
        if np.any(border != 0): return

        if px[y,x] and (not neg):
            if w >= 4 and np.all(self._extract_border(px, x=x, y=y, w=w, h=w) != 0):
                n = self._unpack_number(1 - px, x=x+1, y=y+1, w=w-2, h=w-2)
                return f'v{n}', (w, w)
            else:
                n = self._unpack_number(px, x=x, y=y, w=w, h=w)
                sym = self.symbols.get((w, n))
                if sym is not None:
                    return sym, (w, w)
                return str(n), (w, w)

        n = self._unpack_number(px, x=x, y=y, w=w, h=w)
        return (-n if neg else n), (w + neg, w)


def ocr(px):
    scale = 0
    for i in range(min(*px.shape)):
        if px[i,i] == 0: break
        scale += 1
    px = px[::scale, ::scale]
    
    decoder = Decoder()
    y, x, row = 1, 1, 0
    while y + 1 < px.shape[0]:
        while x + 1 < px.shape[1]:
            r = decoder.decode_symbol(px, x=x, y=y)
            if r:
                n, (h, w) = r
                yield (n, (x*scale, y*scale, (x+w)*scale, (y+h)*scale))
                x += w + 1
                row = max(row, h)
            else:
                x += 1
        else:
            x = 1
            y += row + 1
            row = 0


def ocr_image(im):
    px = (np.array(im)[:,:,0] != 0).astype(np.uint8)
    return ocr(px)


class Svg:
    def __init__(self, width, height, scale=1):
        self.width = width
        self.height = height
        self.scale = scale
        w, h = width * scale, height * scale
        self.so = io.StringIO()
        self._print(f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{w}" height="{h}">')
        self._print(f'<rect width="{w}" height="{h}" style="fill:black" />')

    def __str__(self):
        return self.so.getvalue()

    def _print(self, *args, **kwargs):
        print(*args, file=self.so, **kwargs)

    def close(self):
        self._print('</svg>')

    def rect(self, xywh, fill=None, alpha=None, inset=0):
        style = list()
        if fill: style.append(f'fill:{fill}')
        if alpha: style.append(f'opacity:{alpha}')
        style = ';'.join(style)
        x, y, w, h = np.array(xywh) * self.scale
        if inset:
            x += inset * self.scale
            y += inset * self.scale
            w -= 2 * inset * self.scale
            h -= 2 * inset * self.scale
        self._print(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" style="{style}" />')

    def text(self, xywh, text, fill='yellow'):
        style = list()
        style.append('paint-order: stroke')
        if fill: style.append(f'fill: {fill}')
        style.append('stroke: black')
        sz = 0.1 * self.scale
        style.append(f'stroke-width: {sz}pt')
        sz = 1.9 * self.scale
        style.append(f'font: {sz}pt bold sans')
        style = ';'.join(style)
        x, y, w, h = np.array(xywh) * self.scale
        x += w / 2
        y += h / 2
        self._print(f'<text x="{x}" y="{y}" dominant-baseline="middle" text-anchor="middle" style="{style}">{text}</text>')


def annotate(im, scale=10, pad=3):
    def normalize(im):
        px = (np.array(im)[:,:,0] != 0).astype(np.uint8)
        scale = 0
        for i in range(min(*px.shape)):
            if px[i,i] == 0: break
            scale += 1
        return px[::scale, ::scale]

    px = normalize(im)
    svg = Svg(width=px.shape[1], height=px.shape[0], scale=scale)

    for i, v in np.ndenumerate(px):
        if v:
            y, x = i
            svg.rect((x, y, 1, 1), fill='#fff', inset=0.1)

    for symbol, box in ocr(px):
        x,y,w,h = box
        w -= x
        h -= y
        svg.rect((x,y,w,h), fill='#333', alpha=0.5, inset=-0.2)
        svg.text((x,y,w,h), text=str(symbol))

    svg.close()
    return str(svg)


if __name__ == '__main__':
    import argparse

    def main(fn):
        with Image.open(fn) as im:
            print(annotate(im))

    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='Message image to annotate')
    args = parser.parse_args()

    main(fn=args.input)
