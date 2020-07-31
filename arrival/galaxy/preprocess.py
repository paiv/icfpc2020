#!/usr/bin/env python
import io
import itertools
import sys
from arrival import MachineImage


class Preprocessor:
    def parses(self, text):
        with io.StringIO(text) as fp:
            return self.parse(fp)

    def parse(self, fp):
        tokens = MachineImage.TOKENS

        def ser(t):
            if t.startswith(':') and t[1:].isdigit():
                return [tokens['FUN'], int(t[1:], 10)]
            elif t.isdigit() or (t.startswith('-') and t[1:].isdigit()):
                return [tokens['number'], int(t, 10)]
            elif t == '=':
                return [tokens['DEF']]
            elif t == 'galaxy':
                return [tokens['galaxy'], 0]
            return [tokens[t]]

        machine = list()
        for ln in fp:
            xs = [x for p in map(ser, ln.split()) for x in p]
            s = [tokens['SCAN'], len(xs)] + xs
            machine += s

        machine.append(tokens["GG"])

        return tokens, machine


class Printer:
    def __init__(self, fp):
        self.fp = fp

    def write(self, *args, **kwargs):
        print(*args, file=self.fp, **kwargs)

    def format(self, machine, tokens):
        self.write('// preprocess.py galaxy.txt > galaxy_machine.inc')
        self.write()

        self.write('enum class atom_kind : uint8_t {')
        s = '\n'.join(f'    {k} = {v},' for k,v in tokens.items())
        self.write(s)
        self.write('};')
        self.write()

        scan, fun, df, galaxy = tokens['SCAN'], tokens['FUN'], tokens['DEF'], tokens['galaxy']

        self.write('static const int64_t')
        self.write('galaxy_machine_image[] = {', end='')

        for i, x in enumerate(machine[:-1]):
            if (x == scan) and (i + 5 < len(machine)):
                if ((machine[i+2] == fun) or (machine[i+2] == galaxy)) and (machine[i+4] == df):
                    self.write()
                    self.write('    ', end='')
            self.write(str(x), end=', ')

        self.write()
        self.write(f'    {machine[-1]},')
        self.write('};')


def preprocess(fn='galaxy.txt'):
    fp = sys.stdin if fn == '-' else open(fn)
    try:
        preproc = Preprocessor()
        tokens, machine = preproc.parse(fp)
    finally:
        if fn != '-': fp.close()

    printer = Printer(sys.stdout)
    printer.format(machine, tokens)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    a = parser.add_argument('galaxy', metavar='galaxy.txt')
    args = parser.parse_args()

    preprocess(args.galaxy)
