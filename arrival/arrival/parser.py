class Node:
    def __init__(self):
        self.depth = 0

    def __repr__(self):
        return f'{self.__class__.__name__}'

    def optimize(self, scope):
        return self.reduce(scope, set())

    def reduce(self, scope, seen):
        # print(f'** {id(self)} {repr(self)}.reduce')
        return None


class Function (Node):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg
        self.depth = 1 + arg.depth

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.arg)})'

    def reduce(self, scope, seen):
        if id(self) in seen: return
        seen.add(id(self))

        if (arg := self.arg.reduce(scope, seen)):
            self.arg = arg
            self.depth = 1 + arg.depth
            return self
        return self.invoke(scope)

    def apply(self, arg, scope, seen):
        f = self.invoke(scope)
        return f.apply(arg, scope, seen)

    def invoke(self, scope):
        pass


class BinaryFunction (Function):
    def __init__(self, arg0, arg1):
        super().__init__(Tuple(arg0, arg1))


class TernaryFunction (Function):
    def __init__(self, arg0, arg1, arg2):
        super().__init__(Tuple(arg0, arg1, arg2))


class Partial (Node):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg
        self.depth = 1 + arg.depth

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.arg)})'

    def reduce(self, scope, seen):
        if id(self) in seen: return
        seen.add(id(self))

        if (arg := self.arg.reduce(scope, seen)):
            self.arg = arg
            self.depth = 1 + arg.depth
            return self


class Partial2 (Partial):
    def __init__(self, arg0, arg1):
        super().__init__(Tuple(arg0, arg1))


class AddPartial (Partial):
    def apply(self, arg, scope, seen):
        return AddFunction(self.arg, arg)


class AddFunction (BinaryFunction):
    def invoke(self, scope):
        return self.arg[0].add(self.arg[1], scope)


class CombiBPartial (Partial2):
    def apply(self, arg, scope, seen):
        x = self.arg[1].apply(arg, scope, seen)
        return self.arg[0].apply(x, scope, seen)


class CombiBPartial2 (Partial):
    def apply(self, arg, scope, seen):
        return CombiBPartial(self.arg, arg)


class CombiCPartial (Partial2):
    def apply(self, arg, scope, seen):
        f = self.arg[0].apply(arg, scope, seen)
        return f.apply(self.arg[1], scope, seen)


class CombiCPartial2 (Partial):
    def apply(self, arg, scope, seen):
        return CombiCPartial(self.arg, arg)


class CombiIFunction (Function):
    def apply(self, arg, scope, seen):
        return self.arg.apply(arg, scope, seen)

    def invoke(self, scope):
        return self.arg


class CombiKPartial (Partial):
    def apply(self, arg, scope, seen):
        return self.arg


class CombiSPartial (Partial2):
    def apply(self, arg, scope, seen):
        return CombiSFunction(self.arg[0], self.arg[1], arg)


class CombiSPartial2 (Partial):
    def apply(self, arg, scope, seen):
        return CombiSPartial(self.arg, arg)


class CombiSFunction (TernaryFunction):
    def invoke(self, scope):
        x = self.arg[1].apply(self.arg[2], scope, set())
        f = self.arg[0].apply(self.arg[2], scope, set())
        return f.apply(x, scope, set())


class ConsPartial (Partial):
    def apply(self, arg, scope, seen):
        if isinstance(arg, NilValue):
            return List(self.arg)
        return Cons(self.arg, arg)


class DecrementFunction (Function):
    def invoke(self, scope):
        return self.arg.add(IntValue(-1), scope)


class DivPartial (Partial):
    def apply(self, arg, scope, seen):
        return DivFunction(self.arg, arg)


class DivFunction (BinaryFunction):
    def invoke(self, scope):
        return self.arg[0].div(self.arg[1], scope)


class EqPartial (Partial):
    def apply(self, arg, scope, seen):
        return EqFunction(self.arg, arg)


class EqFunction (BinaryFunction):
    def invoke(self, scope):
        return self.arg[0].equal(self.arg[1], scope)


class FalseFunction (Partial):
    def apply(self, arg, scope, seen):
        return arg


class If0Partial (Partial2):
    def apply(self, arg, scope, seen):
        return If0Function(self.arg[0], self.arg[1], arg)


class If0Partial2 (Partial):
    def apply(self, arg, scope, seen):
        return If0Partial(self.arg, arg)


class If0Function (TernaryFunction):
    def invoke(self, scope):
        return self.arg[1] if isinstance(self.arg[0].equal(IntValue(0), scope), TrueValue) else self.arg[2]


class IncrementFunction (Function):
    def invoke(self, scope):
        return self.arg.add(IntValue(1), scope)


class IsNilFunction (Function):
    def invoke(self, scope):
        return TrueValue() if isinstance(self.arg, NilValue) else FalseValue()


class LessThanPartial (Partial):
    def apply(self, arg, scope, seen):
        return LessThanFunction(self.arg, arg)


class LessThanFunction (BinaryFunction):
    def invoke(self, scope):
        return self.arg[0].less_than(self.arg[1], scope)


class MulPartial (Partial):
    def apply(self, arg, scope, seen):
        return MulFunction(self.arg, arg)


class MulFunction (BinaryFunction):
    def invoke(self, scope):
        return self.arg[0].mul(self.arg[1], scope)


class NegFunction (Function):
    def invoke(self, scope):
        return self.arg.neg(scope)


class NameRef (Node):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def __repr__(self):
        if self.__class__ != NameRef:
            return f'{self.__class__.__name__}()'
        return f'{self.__class__.__name__}({repr(self.name)})'

    def _resolve(self, scope):
        if (g := _Builtins.get(self.name)):
            return g
        if (f := scope.get(self.name)):
            return f
        assert False, (self,)

    def reduce(self, scope, seen):
        # print(f'** {id(self)} {repr(self)}.reduce')
        if id(self) in seen: return
        seen.add(id(self))

        if (self.name in _Builtins):
            return
        if (v := scope.get(self.name)):
            if ((x := v.reduce(scope, seen)) is not None) and (x != v):
                return self

    def apply(self, arg, scope, seen):
        # print(f'** {id(self)} {repr(self)}.apply')
        if (g := _Builtins.get(self.name)):
            return g(arg)
        if (f := scope.get(self.name)):
            if id(self) in seen: return self
            seen.add(id(self))
            if (r := f.apply(arg, scope, seen)):
                return r

    def value(self, scope):
        return self._resolve(scope).value(scope)

    def equal(self, other, scope):
        if isinstance(other, NameRef):
            if (self.name == other.name):
                return TrueValue()
            x = self._resolve(scope)
            y = other._resolve(scope)
            return x.equal(y, scope)

        x = self._resolve(scope)
        return x.equal(other, scope)

    def neg(self, scope):
        x = self._resolve(scope)
        return x.neg(scope)


class Value (Node):
    def parse(value):
        if value == 'nil':
            return NilValue()
        x = int(value, 10)
        return IntValue(x)

    def __init__(self, value):
        super().__init__()
        self._value = value

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self._value)})'

    def value(self, scope):
        return self._value

    def equal(self, other, scope):
        return TrueValue() if (self.value(scope) == other.value(scope)) else FalseValue()


class IntValue (Value):
    def add(self, other, scope):
        return IntValue(self._value + other.value(scope))

    def div(self, other, scope):
        return IntValue(self._value // other.value(scope))

    def less_than(self, other, scope):
        return TrueValue() if (self._value < other.value(scope)) else FalseValue()

    def mul(self, other, scope):
        return IntValue(self._value * other.value(scope))

    def neg(self, scope):
        return IntValue(-self._value)


class TrueValue (NameRef):
    def __init__(self):
        super().__init__('t')


class FalseValue (NameRef):
    def __init__(self):
        super().__init__('f')


class NilValue (NameRef):
    def __init__(self):
        super().__init__('nil')


class Tuple (Value):
    def __init__(self, *args):
        super().__init__(list(args))

    def __getitem__(self, index):
        return self._value[index]

    # def __add__(self, other):
    #     if isinstance(other, Value):
    #         return Tuple(*self.value, other.value)
    #     assert False, (self, other)

    def reduce(self, scope, seen):
        if id(self) in seen: return
        seen.add(id(self))

        for i in range(len(self._value)):
            if (v := self._value[i].reduce(scope, seen)) is not None:
                self._value[i] = v
                return self

class Cons (Value):
    def __init__(self, *args):
        super().__init__(args)

    def reduce(self, scope, seen):
        if id(self) in seen: return
        seen.add(id(self))

        for i in range(len(self._value)):
            if (v := self._value[i].reduce(scope, seen)) is not None:
                self._value[i] = v
                return self
        if isinstance(self._value[1], List):
            return self._value[1].insert(self._value[0])

    def apply(self, arg, scope, seen):
        assert False, (self, arg)


class List (Value):
    def __init__(self, *args):
        super().__init__(args)

    def __getitem__(self, index):
        return self._value[index]

    def insert(self, arg):
        return List(arg, *self._value)

    def reduce(self, scope, seen):
        if id(self) in seen: return
        seen.add(id(self))

        for i in range(len(self._value)):
            if (v := self._value[i].reduce(scope, seen)) is not None:
                self._value[i] = v
                return self


class Apply (Node):
    def __init__(self, f, arg):
        super().__init__()
        self.f = f
        self.arg = arg
        self.depth = 1 + max(f.depth, arg.depth)

    def __repr__(self):
        return f'Apply({repr(self.f)} {repr(self.arg)})'

    def reduce(self, scope, seen):
        # print(f'** {id(self)} {repr(self)}.reduce')
        if id(self) in seen: return
        seen.add(id(self))

        arg = self.arg.reduce(scope, seen)
        if (arg is not None):
            return Apply(self.f, arg)
        f = self.f.reduce(scope, seen)
        if f is not None:
            return Apply(f, self.arg)
        return self.f.apply(self.arg, scope, set())

    def apply(self, arg, scope, seen):
        assert False, (self, arg)


_Builtins = {
    'add': (lambda arg: AddPartial(arg)),
    'b': (lambda arg: CombiBPartial2(arg)),
    'c': (lambda arg: CombiCPartial2(arg)),
    'cons': (lambda arg: ConsPartial(arg)),
    'dec': (lambda arg: DecrementFunction(arg)),
    'div': (lambda arg: DivPartial(arg)),
    'eq': (lambda arg: EqPartial(arg)),
    'f': (lambda arg: FalseFunction(arg)),
    'i': (lambda arg: CombiIFunction(arg)),
    'if0': (lambda arg: If0Partial2(arg)),
    'inc': (lambda arg: IncrementFunction(arg)),
    'isnil': (lambda arg: IsNilFunction(arg)),
    'lt': (lambda arg: LessThanPartial(arg)),
    'mul': (lambda arg: MulPartial(arg)),
    'neg': (lambda arg: NegFunction(arg)),
    'nil': (lambda arg: NilFunction(arg)),
    's': (lambda arg: CombiSPartial2(arg)),
    't': (lambda arg: CombiKPartial(arg)),
}


class Parser:
    def parse_ast(self, tokens):
        stream = iter(tokens)
        def read(): return next(stream, None)
        def ast():
            s = read()
            if s == 'ap':
                return Apply(ast(), ast())
            if (s == 'nil') or s.isdigit() or (s[0] == '-' and s[1:].isdigit()):
                return Value.parse(s)
            if s == '(':
                args = list()
                while True:
                    args.append(ast())
                    s = read()
                    if s == ')':
                        return List(*args)
                    assert s == ',', (args, s)
            return NameRef(s)
        return ast()

    def parse_program(self, text):
        scope = dict()
        for s in text.splitlines():
            tokens = s.split()
            if tokens:
                assert tokens[1] == '='
                scope[tokens[0]] = self.parse_ast(tokens[2:])
        return scope


if __name__ == '__main__':
    from optimizer import Optimizer
    parser = Parser()
    opt = Optimizer()

    import sys; sys.setrecursionlimit(10000)

    with open('../../spec/galaxy.txt') as fp:
        text = fp.read()

    if 0:
        text = '''
        :2048 = ap f :2048
        main = ap :2048 42
        '''

    if 0:
        text = '''
        main = ap ap ap s x0 x1 x2
        '''

    scope = parser.parse_program(text)
    print(repr(scope))
    scope = opt.optimize(scope)
    print(repr(scope))
