#!/usr/bin/env python
import ctypes
import io
import subprocess
import sys
from arrival import MachineImage
from preprocess import Preprocessor
from pathlib import Path


class Galaxy:
    def __init__(self, target='release'):
        self.state = []
        fn = 'libgalaxy' + ('.dylib' if sys.platform == 'darwin' else '.so')
        build_target = (target + '/') if target else ''
        fn = next(Path(__file__).parent.glob('**/' + build_target + fn))
        self.galexy = ctypes.cdll.LoadLibrary(fn)
        p64 = ctypes.POINTER(ctypes.c_int64)
        u32 = ctypes.c_uint32
        self.galexy.evaluate.argtypes = (u32, p64)
        self.galexy.evaluate.restype = p64
        self.galexy.load_machine.argtypes = (p64,)
        self.galexy.load_machine.restype = None

    def load_machine(self, image):
        # print('machine', repr(image))
        data = (ctypes.c_int64 * len(image))(*image)
        self.galexy.load_machine(data)

    def eval(self, *args):
        # print('galaxy', repr(args))
        image = MachineImage().emit_call('galaxy', *args)
        # print('  ', repr(image))
        data = (ctypes.c_int64 * len(image))(*image)
        res = self.galexy.evaluate(len(image), data)
        res = MachineImage().decode_lists(res)
        # print('  =', repr(res))
        return res


def preprocess(fn):
    with open(fn) as fp:
        text = fp.read()

    code, params = text.split('---')

    pr = Preprocessor()
    tokens, machine = pr.parses(code)

    args = dict()
    for s in params.splitlines():
        ps = s.split('=')
        if len(ps) == 2:
            args[ps[0].strip()] = ps[1].strip()

    param = eval(args['params'])
    expect = eval(args['expect'])
    return machine, param, expect


def build(target):
    r = subprocess.run(['make', 'test', f'TEST_TARGET={target}'], stdout=subprocess.DEVNULL)
    r.check_returncode()


def execute(machine, args, target):
    g = Galaxy(target=target)
    g.load_machine(machine)
    if not isinstance(args, tuple):
        args = (args,)
    a = g.eval(*args)
    g.load_machine(machine)
    b = g.eval(*args)
    assert a == b, (a, b)
    return a


def test_one(fn, target):
    machine, args, expects = preprocess(fn)
    results = execute(machine, args, target=target)
    assert results == expects, (results, expects)


def main(fn=None, evaluate=None, scan=None, target='debug'):
    if evaluate:
        args = eval(evaluate)
        g = Galaxy(target=target)
        results = g.eval(args)
        # print(repr(results))

    if fn:
        build(target=target)
        test_one(fn, target=target)

    if scan:
        build(target=target)
        for fn in Path(scan).glob('*.txt'):
            print(fn)
            test_one(fn, target=target)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', help='Test file')
    parser.add_argument('--eval', metavar='ARG')
    parser.add_argument('-d', '--scan', help='All tests in directory')
    parser.add_argument('-t', '--build-target', metavar='TARGET', default='debug')
    args = parser.parse_args()

    main(
        fn=args.test,
        evaluate=args.eval,
        scan=args.scan,
        target=args.build_target
    )
