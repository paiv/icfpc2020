class ConsCodec:
    def encode(self, data):
        if isinstance(data, (list, tuple)):
            if (data == list()) or (data == tuple()):
                return '00'
            if isinstance(data, tuple) and len(data) == 2:
                return '11' + self.encode(data[0]) + self.encode(data[1])
            return '11' + self.encode(data[0]) + self.encode(data[1:])
        n = int(data)
        neg, n = n < 0, (-n if n < 0 else n)
        s = ''
        while n > 0:
            n, t = divmod(n, 2)
            s += '1' if t else '0'
        while len(s) % 4:
            s += '0'
        s += '0' + ('1' * (len(s) // 4))
        return ('10' if neg else '01') + s[::-1]

    def decode(self, text):
        stream = map(int, text)
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
            if not bit: break
            t += 1
        else:
            return

        t *= 4
        n = 0
        while (t > 0) and (bit := read()) is not None:
            n = (n << 1) | bit
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
        if sig == (0, 0):
            return list()
        elif sig == (1, 1):
            return self._load_1d_cons(stream)
        else:
            neg = sig == (1, 0)
            n = self._load_1d_number(stream)
            if n is None: return
            return (-n if neg else n)
