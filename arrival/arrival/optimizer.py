from collections import deque


class Optimizer:
    def optimize(self, scope):
        fringe = deque(scope.items())
        while fringe:
            key, node = fringe.popleft()

            print(repr(key))
            print(repr(node))

            node = node.optimize(scope)
            if node is None: continue

            print('  ', repr(node))
            print()

            scope[key] = node
            fringe.append((key, node))
        return scope
