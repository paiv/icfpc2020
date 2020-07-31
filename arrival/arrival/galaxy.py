import ctypes
import sys
from pathlib import Path
from .space import SpaceClient


_known_tokens = 'ap cons nil neg c b s isnil car eq mul add lt div i t f cdr SCAN number FUN DEF galaxy GG'
_Tokens = {s:i for i, s in enumerate(_known_tokens.split(), 1)}


class AlienProxy:
    def __init__(self):
        pass


class MachineImage:
    TOKENS = dict(_Tokens)

    def emit_call(self, *args):
        ap, num, gg = map(self.TOKENS.__getitem__, 'ap number GG'.split())
        def emit(fn, args):
            fringe = [(fn, args)]
            while fringe:
                fn, args = fringe.pop()
                if fn is None:
                    yield from self.encode_lists(args)
                elif isinstance(args, (list, tuple)) and (len(args) == 0):
                    yield self.TOKENS[fn]
                else:
                    yield ap
                    fringe.append((None, args[-1]))
                    fringe.append((fn, args[:-1]))
        return list(emit(args[0], args[1:]))

    def encode_lists(self, data):
        ap, cons, num, nil, gg = map(self.TOKENS.__getitem__, 'ap cons number nil GG'.split())
        def encode(data):
            fringe = [data]
            while fringe:
                item = fringe.pop()
                if isinstance(item, tuple) and (len(item) == 1):
                    fringe.append(item[0])
                elif isinstance(item, list) and (len(item) == 0):
                    yield nil
                elif isinstance(item, (list, tuple)):
                    yield ap
                    yield ap
                    yield cons
                    fringe.append(item[1:])
                    fringe.append(item[0])
                else:
                    yield num
                    yield int(item)
        return list(encode(data))

    class _partial:
        def __init__(self, arg):
            self.arg = arg
        def __repr__(self):
            return f'Partial({repr(self.arg)})'

    def decode_lists(self, data):
        ap, cons, num, nil, gg = map(self.TOKENS.__getitem__, 'ap cons number nil GG'.split())

        def reduce(stack):
            while (stack[-3] == '$') and (stack[-2] != '$'):
                head, tail = stack[-2], stack[-1]
                if head == cons:
                    xs = self._partial(tail)
                elif isinstance(head, self._partial):
                    if isinstance(tail, list):
                        xs = [head.arg, *tail]
                    elif isinstance(tail, tuple):
                        xs = (head.arg, *tail)
                    else:
                        xs = (head.arg, tail)
                else:
                    raise Exception((head, tail))
                stack[-3:] = [xs]

        stack = ['$', '$']
        i = 0
        while True:
            # print('** ', i, repr(stack), '--', repr(data[i]))
            x = data[i]
            i += 1
            if x == gg: break
            elif x == ap: stack.append('$')
            elif x == nil: stack.append([]); reduce(stack)
            elif x == num: stack.append(data[i]); i += 1; reduce(stack)
            else: stack.append(x)
        return stack[-1]

    def run_tests(self):
        gg, = map(self.TOKENS.__getitem__, 'GG'.split())
        test_cases = [
            [],
            [42],
            (2, 7),
            [(3, 1)],
            [[],[],[]],
            [0, [42, 11, 12], 3, (8, 9)],
        ]
        for data in test_cases:
            image = MachineImage().encode_lists(data)
            image += [gg]
            rev = MachineImage().decode_lists(image)
            assert rev == data, (rev, data)


class Galaxy:
    def __init__(self, target='release', api_host=None, api_key=None):
        self.state = []
        fn = 'libgalaxy' + ('.dylib' if sys.platform == 'darwin' else '.so')
        build_target = (target + '/') if target else ''
        fn = next(Path(__file__).parent.resolve().parent.glob('**/' + build_target + fn))
        print(repr(str(fn)))
        self.galexy = ctypes.cdll.LoadLibrary(fn)
        p64 = ctypes.POINTER(ctypes.c_int64)
        u32 = ctypes.c_uint32
        self.galexy.evaluate.argtypes = (u32, p64)
        self.galexy.evaluate.restype = p64
        self.galexy.load_machine.argtypes = (p64,)
        self.galexy.load_machine.restype = None
        self.space = SpaceClient(api_host=api_host, api_key=api_key)

    def _interact(self, state, event):
        flag, state, data = self._evaluate(state, event)
        if (flag == 0):
            return (state, data)
        return self._interact(state, self._send_to_alien(data))

    def _evaluate(self, state, event):
        self.galexy.load_machine(None)
        image = MachineImage().emit_call('galaxy', state, event)
        data = (ctypes.c_int64 * len(image))(*image)
        res = self.galexy.evaluate(len(image), data)
        res = MachineImage().decode_lists(res)
        # print('<', repr(res))
        return res

    def _send_to_alien(self, data):
        print('<~', repr(data))
        res = self.space.send(data)
        print('~>', repr(res))
        return res

    def _render_frame(self, images):
        self.frame = images

    def eval_step(self, mouse):
        print('>', (self.state))
        print('>', (mouse or (0, 0)))
        (new_state, images) = self._interact(self.state, mouse or (0, 0))
        print('<', (new_state))
        # print('<', (images))
        self.state = new_state
        self._render_frame(images)


if __name__ == '__main__':
    g = Galaxy()
    r = g.eval_step((0,0))
    print(repr(r))
