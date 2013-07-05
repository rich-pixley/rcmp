####
RCMP
####

Rcmp is a more flexible file and directory comparison tool.

Installation
============

Go into the ``python`` folder and install the Python modules. You can either
do it for all users:

.. code:: console

    # python setup.py install

Or just for yourself:

.. code:: console

    $ python setup.py install --user

Usage
=====

The basic idea here is that depending on content, files don't have to
be bitwise identical in order to be equivalent or "close enough".
This is particularly true for things like build directories where
binaries might include otherwise irrelevant nondeterminisms like time
stamps.  Rcmp includes a flexible extension structure to allow for a
living set of file comparisons.

See doc for more info.
