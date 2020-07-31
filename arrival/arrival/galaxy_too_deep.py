import io
import sys
from collections import deque
from conscodec import ConsCodec
from pathlib import Path


def PARSE_NUMBER(s):
    try:
        return int(s)
    except TypeError as e:
        print(repr(s), e, file=sys.stderr)
        return 0


def PARSE_FUNCTIONS(fn):
    def parse_ast(tokens):
        stream = iter(tokens)
        def read(): return next(stream, None)
        stack = ['$', '$']
        while (s := read()) is not None:
            if s == 'ap':
                stack.append('ap')
            else:
                if (s.isdigit() or (s[:1] == '-' and s[1:].isdigit())):
                    s = int(s, 10)
                stack.append(Atom(s))
                while (stack[-3] == 'ap') and (stack[-2] != 'ap'):
                    stack[-3:] = (Ap(stack[-2], stack[-1]), )
        return stack[-1]

    scope = dict()
    with open(fn) as fp:
        for s in fp.readlines():
            tokens = s.split()
            if tokens:
                assert tokens[1] == '='
                scope[tokens[0]] = parse_ast(tokens[2:])
    return scope


def GET_LIST_ITEMS_FROM_EXPR(expr):
    p = cons_to_list(expr)
    if len(p) == 3:
        x,y,z = p
        return (
            list_to_cons(x),
            list_to_cons(y),
            list_to_cons(z),
        )

    print(repr(p))
    raise Exception(('unhandled', p))
    # return (
    #     list_to_cons([0]),
    #     list_to_cons([]),
    #     list_to_cons([]),
    # )


def SEND_TO_ALIEN_PROXY(data):
    print('SEND_TO_ALIEN_PROXY')
    xs = cons_to_list(data)
    print(repr(xs))


Display = dict()

def PRINT_IMAGES(images):
    ps = cons_to_list(images)

    buffer = dict(Display)
    for c, xs in zip('#@?!abcdefghi', ps):
        for p in xs:
            buffer[p] = c
            if c == '#': Display[p] = c

    xmin = min(x for x,y in buffer.keys())
    ymin = min(y for x,y in buffer.keys())
    xo = (-xmin)
    yo = (-ymin)
    w = max(x for x,y in buffer.keys()) + 1 - xmin
    h = max(y for x,y in buffer.keys()) + 1 - ymin
    grid = [['.' for dx in range(w)] for dy in range(h)]
    for (x,y), c in buffer.items():
        grid[y+yo][x+xo] = c

    print(f'offset: ({xo}, {yo})')
    s = '\n'.join(map(''.join, grid))
    print(s)


def REQUEST_CLICK_FROM_USER():
    print('REQUEST_CLICK_FROM_USER')
    x = int(input('> '))
    y = int(input('> '))
    v = (x, y)
    print(repr(v))
    return v


def decode_api_response(text):
    cc = ConsCodec()
    data = cc.decode(text)
    return list_to_cons(data)


class Partial:
    def __init__(self, arg):
        self.arg = arg
    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.arg)})'

def cons_to_list(expr):
    if isinstance(expr, Atom):
        if (expr.name == 'nil'): return []
        return expr.name
    if isinstance(expr.fun, Atom) and (expr.fun.name == 'cons'):
        return Partial(cons_to_list(expr.arg))

    head = cons_to_list(expr.fun)
    if isinstance(head, Partial): head = head.arg

    tail = cons_to_list(expr.arg)
    if isinstance(tail, list):
        return [head, *tail]
    return (head, tail)


def list_to_cons(data):
    def enc(s):
        if (s == list()) or (s == tuple()):
            return nil
        if isinstance(s, (int,str)): return Atom(s)
        if isinstance(s, list):
            return Ap(Ap(cons, enc(s[0])), enc(s[1:]))
        if isinstance(s, tuple):
            if len(s) == 2:
                return Ap(Ap(cons, enc(s[0])), enc(s[1]))
            return Ap(Ap(cons, enc(s[0])), enc(s[1:]))
    return enc(data)


def iterative_eq(a, b):
    fringe = deque([(a, b)])
    while fringe:
        a, b = fringe.popleft()
        if isinstance(a, Atom):
            if (not isinstance(b, Atom)) or (a.name != b.name):
                return
        else:
            if (not isinstance(b, Ap)): return
            fringe.append((a.fun, b.fun))
            fringe.append((a.arg, b.arg))
    return True


class Expr:
    def __init__(self):
        self.evaluated = None
    def __repr__(self):
        return f'{self.__class__.__name__}()'

class Atom (Expr):
    def __init__(self, name):
        super().__init__()
        self.name = name
    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.name)})'
    def __eq__(self, other):
        return isinstance(other, Atom) and (self.name == other.name)

class Ap (Expr):
    def __init__(self, fun, arg):
        super().__init__()
        self.fun = fun
        self.arg = arg
    def __repr__(self):
        # return f'{self.__class__.__name__}({repr(self.fun)} {repr(self.arg)})'
        return f'{self.__class__.__name__}(...)'
    def __eq__(self, other):
        return isinstance(other, Ap) and iterative_eq(self, other)


cons = Atom("cons")
t = Atom("t")
f = Atom("f")
nil = Atom("nil")


class Galaxy:
    def __init__(self, target=None):
        fn = next(Path(__file__).parent.resolve().glob('../../**/spec/galaxy.txt'))
        self.functions = PARSE_FUNCTIONS(fn)
        self.state = nil
        self.mouse = (0, 0)
        self.frame = None

    def interact(self, state, event):
        expr = Ap(Ap(Atom("galaxy"), state), event)
        res = self._eval1(expr)
        # Note: res will be modulatable here (consists of cons, nil and numbers only)
        flag, newState, data = GET_LIST_ITEMS_FROM_EXPR(res)
        if (self._asNum(flag) == 0):
            return (newState, data)
        return self.interact(newState, SEND_TO_ALIEN_PROXY(data))

    def _eval1(self, expr):
        if (expr.evaluated is not None):
            return expr.evaluated
        initialExpr = expr
        while (True):
            result = self._tryEval(expr)
            if (result == expr):
                initialExpr.evaluated = result
                return result
            expr = result

    def _tryEval(self, expr):
        if (expr.evaluated is not None):
            return expr.evaluated
        if isinstance(expr, Atom) and (self.functions.get(expr.name) is not None):
            return self.functions[expr.name]
        if isinstance(expr, Ap):
            fun = self._eval1(expr.fun)
            x = expr.arg
            if isinstance(fun, Atom):
                if (fun.name == "neg"): return Atom(-self._asNum(self._eval1(x)))
                if (fun.name == "i"): return x
                if (fun.name == "nil"): return t
                if (fun.name == "isnil"): return Ap(x, Ap(t, Ap(t, f)))
                if (fun.name == "car"): return Ap(x, t)
                if (fun.name == "cdr"): return Ap(x, f)
            if isinstance(fun, Ap):
                fun2 = self._eval1(fun.fun)
                y = fun.arg
                if isinstance(fun2, Atom):
                    if (fun2.name == "t"): return y
                    if (fun2.name == "f"): return x
                    if (fun2.name == "add"): return Atom(self._asNum(self._eval1(x)) + self._asNum(self._eval1(y)))
                    if (fun2.name == "mul"): return Atom(self._asNum(self._eval1(x)) * self._asNum(self._eval1(y)))
                    if (fun2.name == "div"): return Atom(self._asNum(self._eval1(y)) // self._asNum(self._eval1(x)))
                    if (fun2.name == "lt"): return t if self._asNum(self._eval1(y)) < self._asNum(self._eval1(x)) else f
                    if (fun2.name == "eq"): return t if self._asNum(self._eval1(x)) == self._asNum(self._eval1(y)) else f
                    if (fun2.name == "cons"): return self._evalCons(y, x)
                if isinstance(fun2, Ap):
                    fun3 = self._eval1(fun2.fun)
                    z = fun2.arg
                    if isinstance(fun3, Atom):
                        if (fun3.name == "s"): return Ap(Ap(z, x), Ap(y, x))
                        if (fun3.name == "c"): return Ap(Ap(z, x), y)
                        if (fun3.name == "b"): return Ap(z, Ap(y, x))
                        if (fun3.name == "cons"): return Ap(Ap(x, z), y)
        return expr

    def _evalCons(self, a, b):
        res = Ap(Ap(cons, self._eval1(a)), self._eval1(b))
        res.evaluated = res
        return res

    def _asNum(self, n):
        if isinstance(n, Atom):
            return PARSE_NUMBER(n.name)
        print('not a number', type(n), repr(n), file=sys.stdout)
        return 0

    def click(self, x, y):
        self.mouse = (x, y)

    def render_frame(self, images):
        self.frame = images

    def runloop(self):
        # print('state:')
        # print(repr(cons_to_list(self.state)))

        mouse = self.mouse or (0, 0)
        click = nil
        if mouse:
            self.mouse = None
            click = Ap(Ap(cons, Atom(mouse[0])), Atom(mouse[1]))

        print('>', cons_to_list(self.state))
        print('>', cons_to_list(click))
        (newState, images) = self.interact(self.state, click)
        print('<', cons_to_list(newState))
        print('<', cons_to_list(images))

        self.state = newState
        # PRINT_IMAGES(images)
        self.render_frame(cons_to_list(images))

    def eval_step(self, mouse):
        self.mose = mouse
        return self.runloop()


def main():
    galaxy = Galaxy()
    while True:
        galaxy.runloop()
        click = REQUEST_CLICK_FROM_USER()
        galaxy.mouse = click


if __name__ == '__main__':
    main()
