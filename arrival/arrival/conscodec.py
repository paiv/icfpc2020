
class ConsCodec:
    def encode(self, data):
        if isinstance(data, (list, tuple)):
            if (data == list()) or (data == tuple()):
                return b'00'
            if isinstance(data, tuple) and len(data) == 2:
                return b'11' + self.encode(data[0]) + self.encode(data[1])
            return b'11' + self.encode(data[0]) + self.encode(data[1:])
        n = int(data)
        neg, n = n < 0, (-n if n < 0 else n)
        s = b''
        while n > 0:
            n, t = divmod(n, 2)
            s += b'1' if t else b'0'
        while len(s) % 4:
            s += b'0'
        s += b'0' + (b'1' * (len(s) // 4))
        return (b'10' if neg else b'01') + s[::-1]

    def decode(self, text):
        # import pdb; pdb.set_trace()
        stream = iter(text)
        read = lambda: next(stream, None)

        sig = read(), read()
        t = self._load_1d_token(stream, sig)
        if (t is None) or (read() is not None):
            return
        return t

    def _load_1d_number(self, stream):
        read = lambda: next(stream, None)
        t = 0
        while (bit := read()) is not None:
            if bit == 48: break
            t += 1
        else:
            return

        t *= 4
        n = 0
        while (t > 0) and (bit := read()) is not None:
            n = (n << 1) | (1 if bit != 48 else 0)
            t -= 1

        if t != 0: return
        return n

    def _load_1d_cons(self, stream):
        read = lambda: next(stream, None)
        def elem():
            sig = read(), read()
            return self._load_1d_token(stream, sig)
        if (a := elem()) is None: return
        if (b := elem()) is None: return
        elif isinstance(b, list):
            return [a, *b]
        elif isinstance(b, tuple):
            return (a, *b)
        return (a, b)

    def _load_1d_token(self, stream, sig):
        if sig == (48, 48):
            return list()
        elif sig == (49, 49):
            return self._load_1d_cons(stream)
        else:
            neg = sig == (49, 48)
            n = self._load_1d_number(stream)
            if n is None: return
            return (-n if neg else n)


if __name__ == '__main__':
    c = ConsCodec()
    class R:
        def __init__(self, s, v):
            self.s = s
            self.v = v
        def __eq__(self, other):
            if self.v == other: return True
            assert False, (self.s, self.v, other)
    def te(s):
        return R(s, c.encode(s))
    def td(s):
        return R(s, c.decode(s))

    te([]) == b'00'
    te([[]]) == b'110000'
    te([0]) == b'1101000'
    te((1, 2)) == b'110110000101100010'
    te([1, 2]) == b'1101100001110110001000'
    te([(1, (2, 3), 4)]) == b'11 11 01100001 11 11 01100010 01100011 01100100 00'.replace(b' ', b'')

    td(b'00') == []
    td(b'110000') == [[]]
    td(b'1101000') == [0]
    td(b'110110000101100010') == (1, 2)
    td(b'1101100001110110001000') == [1, 2]
    td(b'111101100001111101100010011000110110010000') == [(1, (2, 3), 4)]

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--decode', metavar='MSG')
    args = parser.parse_args()

    if args.decode:
        print(c.decode(args.decode))
