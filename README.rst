####
RCMP
####

Rcmp is a more flexible file and directory comparison tool.

Installation
============

Install the Python modules. You can either do it for all users:

.. code:: console

    # python setup.py install

Or just for yourself:

.. code:: console

    $ python setup.py install --user

Unit Tests
==========

You can run the unit tests using "make check" but this currently
presupposes some things like a globally installed version of
virtualenv.

Usage
=====

The basic idea here is that depending on content, files don't have to
be bitwise identical in order to be equivalent or "close enough".
This is particularly true for things like build directories where
binaries might include otherwise irrelevant nondeterminisms like time
stamps.  Rcmp includes a flexible extension structure to allow for a
living set of file comparisons.

See doc for more info.
