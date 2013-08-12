from __future__ import print_function

class Thingy(object):
    @staticmethod
    def m1(whatever):
        return whatever + 1

    @staticmethod
    def m2(whatever):
        return whatever + 2

    m = m1

# This line works.
print('first is {}'.format(Thingy.m(1)))

Thingy.m = Thingy.m2

# this line fails with:
#   TypeError: unbound method m2() must be called with Thingy instance as first argument (got int instance instead)

print('second is {}'.format(Thingy.m(1)))
