#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Time-stamp: <03-Jul-2013 15:27:04 PDT by rich@noir.com>

# Copyright © 2013 K Richard Pixley
# Copyright (c) 2010 - 2012 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
##############
:py:mod:`RCMP`
##############

:py:mod:`Rcmp` is a more flexible replacement for :py:mod:`filecmp`
from the standard `Python <http://python.org>`_ library.

The basic idea here is that depending on content, files don't always
have to be *entirely* bitwise identical in order to be equivalent or
"close enough" for many purposes like comparing the results of two
builds.  For example, some (broken) file formats embed a time stamp
indicating the time when a file was produced even though the file
system already tracks this information.  Build the same file twice and
the two copies will initially appear to be different due to the
embedded time stamp.  Only when the irrelevant embedded time stamp
differences are ignored do the two files show out to otherwise be the
same.

:py:mod:`Rcmp` includes a flexible extension structure to allow for precisely
these sorts of living and evolving comparisons.

Extended Path Names
===================

:py:mod:`Rcmp` is capable of recursively descending into a number
of different file types including:

* file system directories
* archival and aggregating types including:

  * `ar <http://en.wikipedia.org/wiki/Ar_%28Unix%29>`_
  * `cpio <http://en.wikipedia.org/wiki/Cpio>`_
  * `tar <http://en.wikipedia.org/wiki/Tar_%28file_format%29>`_

* compressed files including:

  * `zip <http://en.wikipedia.org/wiki/Zip_%28file_format%29>`_
  * `gzip <http://en.wikipedia.org/wiki/Gzip>`_

In order to describe file locations which may extend beyond the
traditional file system paths, :py:mod:`rcmp` introduces an extended
path naming scheme.  Traditional paths are described using the
traditional slash separated list of names, :file:`/etc/hosts`.  And
components which are included in other files, like a file located
*within* a `tar <http://en.wikipedia.org/wiki/Tar_%28file_format%29>`_
archive, are described using a sequence of brace encapsulated file
format separaters.  So, for instance, a file named :file:`foo` located
within a gzip compressed, (:file:`.gz`), tar archive named
:file:`tarchive.tar` would be described as
:file:`tarchive.tar.gz{{gzip}}tarchive.tar{{tar}}foo`.  And these can
be combined as with
:file:`/home/rich/tarchive.tar.gz{{gzip}}tarchive.tar{{tar}}foo`.

Items which are not in the file system proper are referred to
internally as being "boxed".

Script Usage
============

:py:mod:`Rcmp` is both a library and a command line script for driving
the library.

Class Architecture
==================

.. autoclass:: Item
   :members:

.. autoclass:: Items
   :members:

.. autoclass:: Same
   :members:

.. autoclass:: Different
   :members:

.. autoclass:: Comparator
   :members:

.. autoclass:: Aggregator
   :members:

.. autoclass:: Comparison
   :members:

.. autoclass:: ComparisonList
   :members:

Comparators
===========

Listed in default order of application:

.. autoclass:: NoSuchFileComparator
.. autoclass:: InodeComparator
.. autoclass:: EmptyFileComparator
.. autoclass:: DirComparator
.. autoclass:: ArMemberMetadataComparator
.. autoclass:: BitwiseComparator
.. autoclass:: SymlinkComparator

.. autoclass:: BuriedPathComparator

.. autoclass:: ElfComparator
.. autoclass:: ArComparator
.. autoclass:: AMComparator
.. autoclass:: ConfigLogComparator
.. autoclass:: KernelConfComparator
.. autoclass:: ZipComparator
.. autoclass:: TarComparator
.. autoclass:: GzipComparator
.. autoclass:: CpioMemberMetadataComparator
.. autoclass:: CpioComparator
.. autoclass:: DateBlotBitwiseComparator
.. autoclass:: FailComparator

Utilities
=========

.. autofunction:: date_blot
.. autofunction:: ignoring

Exceptions
==========

.. autoexception:: RcmpException
.. autoexception:: IndeterminateResult

Logging strategy:
=================

Rcmp uses the python standard logging facility.  The only non-obvious
bits are that definitive differences are logged at WARNING level.
Definitive Sames are logged at WARNING - 1.  And indefinite results
are logged at WARNING - 2.  This allows for linearly increasing
volumes of logging info starting with the information that is usually
more important first.

.. Note:: I keep thinking that it would be better to create an
   IgnoringComparator that simply returned Same.  It would make much
   of the code much simpler.  However, it would mean that we'd build
   entire trees in some cases and compare them all just to produce
   constants.  This way we clip the tree.
"""

from __future__ import print_function, unicode_literals

__docformat__ = 'restructuredtext en'

__all__ = [
    # basics
    'Item',
    'Items',
    'Same',
    'Different',
    'Comparator',
    'Aggregator',
    'Comparison',
    'ComparisonList',

    # utilities
    'ignoring',
    'date_blot'

    # comparators
    'NoSuchFileComparator',
    'InodeComparator',
    'EmptyFileComparator',
    'DirComparator',
    'ArMemberMetadataComparator',
    'BitwiseComparator',
    'SymlinkComparator',
    'BuriedPathComparator',
    'ElfComparator',
    'ArComparator',
    'AMComparator',
    'ConfigLogComparator',
    'KernelConfComparator',
    'ZipComparator',
    'TarComparator',
    'GzipComparator',
    'CpioMemberMetadataComparator',
    'CpioComparator',
    'DateBlotBitwiseComparator',
    'FailComparator',
]

import StringIO
import abc
import difflib
import errno
import fnmatch
import gzip
import logging
import mmap
import operator
import os
import re
import stat
import sys
import tarfile
import zipfile

import elffile
import arpy
import cpiofile

DIFFERENCES = logging.WARNING
SAMES = logging.WARNING - 1
INDETERMINATES = logging.WARNING - 2

logging.addLevelName(DIFFERENCES, 'differences')
logging.addLevelName(SAMES, 'sames')
logging.addLevelName(INDETERMINATES, 'indeterminates')

logger = logging.getLogger(__name__)

import pprint
pp = pprint.PrettyPrinter()

# The point of this contortion is to get a logger per class which
# includes the name of the class.  There's another way to do this
# involving metaclasses that allows for inheritance rather than
# needing to decorate each class individually but I haven't yet
# wrapped my brain around metaclasses.

def _loggable(cls):
    cls.logger = logging.getLogger('{0}.{1}'.format(__name__, cls.__name__))
    return cls


class Item(object):
    """
    Things which can be compared are represented internally by
    instances of class :py:class:`Item`.  These can be items in the
    file system, like a file or directory, or in an archive, like an
    archive member.

    This is used for caching the results from calls like stat and for
    holding content.

    :param name: file system name
    :type name: string
    """

    import stat

    def __init__(self, name):
        self._name = name
        self._statbuf = False
        self._fd = False
        self._content = False
        self._link = False
        self._size = None

    @property
    def name(self):
        """
        name in the extended file system name space of this :py:class:`Item`.

        :rtype: string
        """
        return self._name

    @property
    def fd(self):
        """
        If we have a file descriptor, return it.  If not, then open one,
        cache it, and return it.

        :rtype: file
        """
        if self._fd == False:
            self._fd = open(self.name, 'rb')
            # print('fd is {0} for {1}'.format(self._fd.fileno(),
            #                                  self.name),file=sys.stderr)

        return self._fd

    def close(self):
        """
        Close any outstanding file descriptor if relevant.
        """
        if not self.boxed:
            if self._fd:
                self.fd.close()

            self._fd = False
            self._content = False

    @property
    def content(self):
        """
        The contents of the entire file, in memory.

        :rtype: bytearray or possibly an mmap'd section of file.
        """
        if self._content is False:
            # print('self = {0}'.format(self))
            # print('self.fd = {0}'.format(self.fd))
            # print('self.fd.fileno() = {0}'.format(self.fd.fileno()))
            # print('self.fd.closed = {0}'.format(self.fd.closed))
            # print('self.fd.name = {0}'.format(self.fd.name))

            if self.size > 0:
                self._content = mmap.mmap(self.fd.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ)
            else:
                self._content = b''

        return self._content

    @property
    def stat(self):
        """
        If we have a statbuf, return it.

        If not, then look one up, cache it, and return it.

        :rtype: statbuf
        """
        if not self._statbuf:
            try:
                self._statbuf = os.lstat(self.name)
            except OSError as (err, strerror):
                if err != errno.ENOENT:
                    raise

        return self._statbuf

    @property
    def exists(self):
        """
        Check for existence.  Boxed items always exist.  Unboxed items
        exist if they exist in the file system.

        :rtype: boolean
        """
        return self.boxed or (self.stat is not False)

    @property
    def inode(self):
        """
        Return the inode number from stat.

        :rtype: string
        """
        return self.stat.st_ino

    @property
    def device(self):
        """
        Return device number from stat.

        :rtype: string
        """
        return self.stat.st_dev

    @property
    def size(self):
        """
        Return our size.  Look it up in stat, (and cache the result), if
        we don't already know what it is.

        :rtype: int
        """
        if self._size is None:
            self._size = self.stat.st_size

        return self._size

    @property
    def isdir(self):
        """
        Return True if and only if we are represent a file system
        directory.

        :rtype: boolean
        """
        return (not self.boxed) and stat.S_ISDIR(self.stat.st_mode)

    @property
    def isreg(self):
        """
        Return True if and only if we represent a regular file.

        :rtype: boolean
        """
        return self.boxed or stat.S_ISREG(self.stat.st_mode)

    @property
    def islnk(self):
        """
        Return True if and only if we represent a symbolic link.

        :rtype: boolean
        """
        return (not self.boxed) and stat.S_ISLNK(self.stat.st_mode)

    @property
    def link(self):
        """
        Return a string representing the path to which the symbolic link
        points.  This presumes that we are a symbolic link.

        :rtype: string
        """
        if not self._link:
            self._link = os.readlink(self.name)

        return self._link

    @property
    def boxed(self):
        """
        Returns True if and only if we are "boxed". That is, if we are not
        located directly in the file system but instead are
        encapsulated within some other file.

        :rtype: boolean
        """
        return hasattr(self, 'box')

class Items(object):
    """
    There is a global set of all instances of class :py:class:`Item`
    stored in the singular class :py:class:`Items`.

    This exists primarily to prevent us from creating a duplicate
    :py:class:`Item` for the same path name.

    .. note:: The class is used directly here as a global aggregator,
       a singleton.  It is never instantiated but instead the class
       itself is used as a singleton.
    """

    _content = {}

    @classmethod
    def find_or_create(cls, name):
        """
        Look up an :py:class:`Item` with *name*.  If necessary, create it.

        :param name: the name of the :py:class`Item` to look up
        :type name: string
        :rtype: :py:class:`Item`
        """
        ### FIXME: I suspect this is extraneous.  It breaks zipfiles
        ### with foo/.  Remove it once it's settled.
        # name = os.path.abspath(name)
        if name in cls._content:
            return cls._content[name]
        else:
            x = Item(name)
            cls._content[name] = x
            return x

    @classmethod
    def delete(cls, name):
        """
        Delete an :py:class:`Item` from the set.

        :param name: name of the :py:class:`Item` to be deleted.
        :type name: string
        """
        del cls._content[name]

class Same(object):
    """
    Returned to indicate an authoritative claim of sufficient
    identicality.  No further comparators need be tried.

    .. note:: The class itself is used as a constant.  It is never
       instantiated.
    """
    pass

class Different(object):
    """
    Returned to indicate an authoritative claim of difference.  No
    further comparators need be tried.

    .. note:: The class itself is used as a constant.  It is never
       instantiated.
    """
    pass

@_loggable
class Comparator(object):
    """
    Represents a single comparison heuristic.  This is an abstract
    class.  It is intended solely to act as a base class for
    subclasses.  It is never instantiated.

    Subclasses based on :py:class:`Comparator` implement individual
    heuristics for comparing items when applied to a
    :py:class:`Comparison`.  There are many :py:class:`Comparator`
    subclasses included.

    There are no instantiation variables nor properties.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _applies(self, thing):
        return False

    def applies(self, comparison):
        """
        Return True if and only if we apply to the given comparison.

        :type comparison: :py:class:`Comparison`
        :rtype: boolean
        """
        return reduce(operator.iand, [self._applies(i) for i in comparison.pair])

    @abc.abstractmethod
    def cmp(self, comparison):
        """
        Apply ourselves to the given :py:class:`Comparison`.

        If can make an authoritative determination about whether the
        :py:class:`Items` are alike then return either
        :py:class:`Same` or :py:class:`Different`.  If we can make no
        such determination, then return a non-True value.

        :type comparison: :py:class:`Comparison`
        :rtype: :py:class:`Same`, :py:class:`Different`, or a non-True value
        """
        self.logger.error('{0}.cmp() isn\'t overridden.'.format(self.__class__.__name__))

        raise NotImplementedError
        return False

    def _log_item(self, item):
        if item.exists and item.islnk:
            return (item.name, item.link)
        else:
            return item.name

    def _log_string(self, s, comparison):
        return '{0} {1}\n{2}'.format(s, self.__class__.__name__,
                                     pp.pformat([self._log_item(i) for i in comparison.pair]))

    def _log_unidiffs(self, content, names):
        try:
            self.logger.log(DIFFERENCES,
                            '\n'.join(difflib.unified_diff(content[0].split('\n'),
                                                           content[1].split('\n'),
                                                           names[0], names[1],
                                                           '', '', 3, '')))
        except UnicodeError:
            pass

    def _log_unidiffs_comparison(self, comparison):
        self._log_unidiffs([i.content[:] for i in comparison.pair],
                           [i.name for i in comparison.pair])

    def _log_different(self, comparison):
        self.logger.log(DIFFERENCES, self._log_string('Different', comparison))

    def _log_same(self, comparison):
        self.logger.log(SAMES, self._log_string('Same', comparison))

    def _log_indeterminate(self, comparison):
        self.logger.log(INDETERMINATES, self._log_string('Indeterminate', comparison))


def date_blot(input_string):
    """Convert dates embedded in a string into innocuous constants of uniform length.
    
    :param input_string: input string
    :rtype: string
    """
    retval = input_string

    try:
        # Sun Feb 13 12:29:28 PST 2011
        retval = re.sub(r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) *[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} (PST|PDT) [0-9]{4}',
                        'Day Mon 00 00:00:00 LOC 2011',
                        retval)

        retval = re.sub(r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) *[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}',
                        'Day Mon 00 00:00:00 2011',
                        retval)

        # 13 FEB 2011 11:52
        retval = re.sub(r'(?i) *[0-9]{1,2} (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC) [0-9]{4} [0-9]{2}:[0-9]{2}',
                        '00 MON 2011 00:00',
                        retval)

        # "April  7, 2011"
        retval = re.sub(r'(January|February|March|April|May|June|July|August|September|October|November|December) *[0-9]{1,2}\\?, [0-9]{4}',
                        'Month 00, 2011',
                        retval)

        # Wed Apr 13 2011
        retval = re.sub(r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) *[0-9]{1,2} *[0-9]{4}',
                        'Day Mon 00 2011',
                        retval)

        # Wed 13 Apr 2011
        retval = re.sub(r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat) *[0-9]{1,2} *(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) *[0-9]{4}',
                        'Day 00 Mon 2011',
                        retval)

        # Wed 13 April 2011
        retval = re.sub(r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat) *[0-9]{1,2} *(January|February|March|April|May|June|July|August|September|October|November|December) *[0-9]{4}',
                        'Day 00 Month 2011',
                        retval)

        # 2011-04-13
        retval = re.sub(r'20*[0-9]{2}-*[0-9]{2}-*[0-9]{2}',
                        '2011-00-00',
                        retval)

        # Apr 2011
        retval = re.sub(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [0-9]{4}',
                        'Mon 2011',
                        retval)

        # 00:00:00
        retval = re.sub(r'[0-9]{2}:[0-9]{2}:[0-9]{2}',
                        '00:00:00',
                        retval)

        # 2011-07-11T170033Z
        retval = re.sub(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z',
                        '00000000T000000Z',
                        retval)

    except UnicodeError:
        pass

    return retval

def ignoring(ignores, fname):
    """
    Given a list of file names to be ignored and a specific file name
    to check, return the first ignore pattern from the list that
    matches the file name.

    :param ignores: ignore patterns
    :type ignores: list of strings
    :param fname: file name to check
    :type fname: string
    :rtype: string or False (Can be used as a predicate.)
    """
    for ignore in ignores:
        if fnmatch.fnmatch(fname, ignore):
            return ignore

    return False

@_loggable
class InodeComparator(Comparator):
    """
    Objects with the same inode and device are identical.
    """

    def _applies(self, thing):
        return not thing.boxed

    def cmp(self, comparison):
        if (reduce(operator.eq, [i.inode for i in comparison.pair])
            and reduce(operator.eq, [i.device for i in comparison.pair])):
            self._log_same(comparison)
            return Same
        else:
            self._log_indeterminate(comparison)
            return False

@_loggable
class EmptyFileComparator(Comparator):
    """
    Two files which are each empty are equal.  In particular, we don't
    need to open them or read them to make this determination.
    """

    def _applies(self, thing):
        return thing.isreg

    def cmp(self, comparison):
        if (comparison.pair[0].size == 0
            and comparison.pair[1].size == 0):
            self._log_same(comparison)
            return Same
        else:
            self._log_indeterminate(comparison)
            return False

class RcmpException(Exception):
    """Base class for all :py:mod:`rcmp` exceptions"""
    pass

class IndeterminateResult(RcmpException):
    """
    Raised when we can't make any authoritative determination.  At the
    top level, this is an error condition as this case indicates that
    we've failed to accomplish our job.  Note that this is
    significantly different from the non-True value returned by
    :py:class:`Comparator` subclasses to indicate that they have no
    authoritative result.
    """
    pass

class BadZipfile(RcmpException):
    """Raised when we fail to open a zip archive"""
    pass

class _Boxer(object):
    """
    just for aggregation, not intended for instantiation.
    """

    def __init__(self, joiner='/'):
        self.joiner = joiner

    def join(self, left, right):
        return '{0}{1}{2}'.format(left, self.joiner, right)

    def split(self, path):
        return path.split(self.joiner)

class Aggregator(Comparator):
    """
    This is an abstract base class intended for things which are
    composed of other things.  So, for instance, a directory, or a
    file archive.
    """
    __metaclass__ = abc.ABCMeta

    _comparators = []
    """
    comparators to be used by children
    """

    _comparisons = []
    """
    a list of children to be compared
    """

    @abc.abstractproperty
    def _boxer(self):
        """
        An instance of :py:class:_Boxer: to use for path manipulation.
        """
        return None

    @abc.abstractmethod
    def _applies(self, thing):
        raise NotImplementedError

    def __init__(self, comparators=[]):
        self._comparators = comparators
        self._comparisons = []

    def _no_mate(self, name, logger):
        self.logger.log(DIFFERENCES, 'Different {0} No mate: {1}'.format(self.__class__.__name__, name))

    @abc.abstractmethod
    def _expand(self, ignoring, box):
        """
        Given an :py:class:`Thing`, return a list of it's components.
        """
        self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, box.name))
        raise NotImplementedError

    @abc.abstractmethod
    def _mates(self, item, box):
        """
        Return true if *item* has a mate in *box*.
        """
        raise NotImplementedError

    def _outer_join(self, comparison, invert=False, spool=True):
        # left outer join
        result = False

        if invert:
            rbox, lbox = [p for p in comparison.pair]
        else:
            lbox, rbox = [p for p in comparison.pair]

        for name, litem in self._expand(comparison.ignoring, lbox):
            rname = self._boxer.join(rbox.name, name)
            ignore = comparison.ignoring(rname)
            if not ignore:
                ritem = Items.find_or_create(rname)
                if self._mates(ritem, rbox):
                    if spool:
                        comparison.children.append(Comparison(litem=litem,
                                                              ritem=ritem,
                                                              comparators=comparison.comparators,
                                                              ignores=comparison.ignores,
                                                              exit_asap=comparison.exit_asap))
                else:
                    self._no_mate(litem.name, logger)
                    result = Different

        return result

    def _left_outer_join(self, comparison):
        return self._outer_join(comparison)

    def _right_outer_join(self, comparison):
        # we should already have a comparison for this
        # pair but I'd need to rearrange the ordering to
        # do an assert to prove it.
        return self._outer_join(comparison, invert=True, spool=False)

    def _inner_join(self, comparison):
        # inner join
        for c in comparison.children:
            r = c.cmp()

            if not r:
                self._log_indeterminate(comparison)
                raise IndeterminateResult

            if r == Different:
                self._log_different(comparison)
                return Different

    def cmp(self, comparison):
        """
        Compare our lists and return the result.
        """
        if (self._left_outer_join(comparison) == Different
            or self._right_outer_join(comparison) == Different):
            # already logged earlier
            return Different

        if self._inner_join(comparison) == Different:
            # already logged earlier
            return Different

        self._log_same(comparison)
        return Same

@_loggable
class DirComparator(Aggregator):
    """
    Objects which are directories are special.  They match if their
    contents match.
    """

    _boxer = _Boxer('/')

    def _applies(self, thing):
        return (not thing.boxed) and thing.isdir

    def _expand(self, ignoring, box):
        self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, box.name))

        for fname in os.listdir(box.name):
            fullname = self._boxer.join(box.name, fname)
            self.logger.log(logging.DEBUG, '{0} considers {1}'.format(self.__class__.__name__, fullname))

            ignore = ignoring(fullname)
            if ignore:
                self.logger.log(SAMES, 'Ignoring {0} cause {1}'.format(fullname, ignore))
                continue

            self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, fullname))
            item = Items.find_or_create(fullname)

            yield (fname, item)

    def _mates(self, item, container):
        """
        Return true if *item* has a mate in *container*.
        """
        return item.exists


@_loggable
class BitwiseComparator(Comparator):
    """
    Objects which are bitwise identical are close enough.
    """

    def _applies(self, thing):
        return thing.isreg

    def cmp(self, comparison):
        if (reduce(operator.eq, [i.size for i in comparison.pair])
            and comparison.pair[0].content.find(comparison.pair[1].content) == 0):
            self._log_same(comparison)
            retval = Same
        else:
            self._log_indeterminate(comparison)
            retval = False

        for i in comparison.pair:
            i.close()

        return retval


@_loggable
class DateBlotBitwiseComparator(Comparator):
    """
    Objects which are bitwise identical after date blotting are close
    enough.  But this should only be tried late.
    """

    def _applies(self, thing):
        return thing.isreg

    def cmp(self, comparison):
        if (reduce(operator.eq, [date_blot(i.content) for i in comparison.pair])):
            self._log_same(comparison)
            retval = Same
        else:
            self._log_indeterminate(comparison)
            retval = False

        for i in comparison.pair:
            i.close()

        return retval


@_loggable
class NoSuchFileComparator(Comparator):
    """
    Objects are different if either one is missing.
    """
    # FIXME: perhaps this should return same if both are missing.

    def _applies(self, thing):
        return True

    def cmp(self, comparison):
        e = [i.exists for i in comparison.pair]
        if reduce(operator.ne, e):
            self._log_different(comparison)
            return Different

        if e[0] is False:
            self._log_same(comparison)
            return Same

        self._log_indeterminate(comparison)
        return False

@_loggable
class ElfComparator(Comparator):
    """
    Elf files are different if any of the important sections are
    different.
    """

    _magic = b'\x7fELF'

    def _applies(self, thing):
        return thing.content.find(self._magic, 0, len(self._magic)) == 0

    def cmp(self, comparison):
        e = [(i.content.find(self._magic, 0, len(self._magic)) == 0) for i in comparison.pair]
        if not reduce(operator.iand, e):
            self._log_different(comparison)
            return Different

        e = [elffile.open(name=i.name, block=i.content) for i in comparison.pair]
        if e[0].close_enough(e[1]):
            self._log_same(comparison)
            return Same
        else:
            self._log_different(comparison)
            return Different

@_loggable
class ArMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of an ar archive.
    """
    def _applies(self, thing):
        return thing.boxed and hasattr(thing.box, 'ar')

    def cmp(self, comparison):
        (left, right) = [i.member.header for i in comparison.pair]

        if (left.uid == right.uid
            and left.gid == right.gid
            and left.mode == right.mode):
            return False
        else:
            self._log_different(comparison)
            return Different


import contextlib
@contextlib.contextmanager
def openar(filename, fileobj):
    """
    """
    ar = arpy.Archive(filename=filename, fileobj=fileobj)
    ar.read_all_headers()
    yield ar
    ar.close()

@_loggable
class ArComparator(Aggregator):
    """
    Ar archive files are different if any of the important members are
    different.
    """

    _magic = b'!<arch>\n'

    _boxer = _Boxer('{ar}')

    def _applies(self, thing):
        return thing.content.find(self._magic, 0, len(self._magic)) == 0

    def _expand(self, ignoring, box):
        self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, box.name))

        for fname in box.ar.archived_files.keys():
            fullname = self._boxer.join(box.name, fname)
            ignore = ignoring(fullname)
            if ignore:
                self.logger.log(SAMES, 'Ignoring {0} cause {1}'.format(fullname, ignore))
                continue

            item = Items.find_or_create(fullname)
            if not item._content:
                assert not hasattr(item, 'box')

                item.member = box.ar.archived_files[fname]
                item._size = item.member.header.size
                item._content = item.member.read()
                item.box = box

            yield (fname, item)

    def _mates(self, item, box):
        return self._boxer.split(item.name)[-1] in box.ar.archived_files.keys()

    def cmp(self, comparison):
        with contextlib.nested(openar(comparison.pair[0].name,
                                       StringIO.StringIO(comparison.pair[0].content[:])),
                               openar(comparison.pair[1].name,
                                       StringIO.StringIO(comparison.pair[1].content[:]))) as (comparison.pair[0].ar,
                                                                                              comparison.pair[1].ar):
            return Aggregator.cmp(self, comparison)


@_loggable
class CpioMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of a cpio archive.
    """
    def _applies(self, thing):
        return thing.boxed and hasattr(thing.box, 'cpio')

    def cmp(self, comparison):
        (left, right) = [i.member for i in comparison.pair]

        if (left.mode == right.mode
            and left.uid == right.uid
            and left.gid == right.gid
            and left.rdevmajor == right.rdevmajor
            and left.rdevminor == right.rdevminor
            and left.filesize == right.filesize):
            return False
        else:
            self._log_different(comparison)
            return Different


@contextlib.contextmanager
def opencpio(filename, guts):
    """
    """
    cpio = cpiofile.CpioFile().open(name=filename, block=guts)
    yield cpio
    cpio.close()

@_loggable
class CpioComparator(Aggregator):
    """
    Cpio archive files are different if any of the important members
    are different.
    """

    _boxer = _Boxer('{cpio}')

    def _applies(self, thing):
        return bool(cpiofile.valid_magic(thing.content))

    def _expand(self, ignoring, box):
        """
        Yields pairs, (filename, Item), of the contents of *box*.
        """
        self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, box.name))

        for fname in box.cpio.names:
            fullname = self._boxer.join(box.name, fname)
            ignore = ignoring(fullname)
            if ignore:
                self.logger.log(SAMES, 'Ignoring {0} cause {1}'.format(fullname, ignore))
                continue

            item = Items.find_or_create(fullname)
            if not item._content:
                if item.boxed:
                    # FIXME: remove these asserts when I'm convinced it's ok
                    assert item.member == box.cpio.get_member(fname)
                    assert item._size == item.member.filesize
                    assert item._content == item.member.content
                    assert item.box == box
                else:
                    item.member = box.cpio.get_member(fname)
                    item._size = item.member.filesize
                    item._content = item.member.content
                    item.box = box

            yield (fname, item)

    def _mates(self, item, box):
        return self._boxer.split(item.name)[-1] in box.cpio.names

    def cmp(self, comparison):
        with contextlib.nested(opencpio(comparison.pair[0].name, comparison.pair[0].content[:]),
                               opencpio(comparison.pair[1].name, comparison.pair[0].content[:])) as (comparison.pair[0].cpio,
                                                                                                     comparison.pair[1].cpio):
            return Aggregator.cmp(self, comparison)


@_loggable
class TarMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of an ar archive.
    """
    def _applies(self, thing):
        return thing.boxed and hasattr(thing.box, 'tar')

    def cmp(self, comparison):
        (left, right) = [i.member for i in comparison.pair]

        if (left.mode == right.mode
            and left.type == right.type
            and left.linkname == right.linkname
            and left.uid == right.uid
            and left.gid == right.gid
            and left.uname == right.uname
            and left.gname == right.gname):
            return False
        else:
            self._log_different(comparison)
            return Different


# TarFile didn't become a context manager until 2.7.  :\.
import contextlib
@contextlib.contextmanager
def opentar(filename, mode, fileobj):
    """
    .. todo:: remove opentar once we move to python-2.7
    """
    tar = tarfile.open(name=filename, mode=mode, fileobj=fileobj)
    yield tar
    tar.close()

@_loggable
class TarComparator(Aggregator):
    """
    Tar archive files are different if any of the important members
    are different.

    .. note:: must be called before GzipComparator in order to exploit
       the Python tarfile module's ability to open compressed
       archives.
    """

    _boxer = _Boxer('{tar}')

    def _applies(self, thing):
        # NOTE: this doesn't catch old style tar archives but if we're
        # lucky, we won't need to.

        try:
            tarfile.open(fileobj=StringIO.StringIO(thing.content[:])).close()

        except:
            return False

        return True

        #return (thing.content.find('ustar', 257, 264) > -1)
                

    def _expand(self, ignoring, box):
        """
        Yields pairs, (filename, Item), of the contents of *box*.
        """
        self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, box.name))

        for fname in box.tar.getnames():
            fullname = self._boxer.join(box.name, fname)
            ignore = ignoring(fullname)
            if ignore:
                self.logger.log(SAMES, 'Ignoring {0} cause {1}'.format(fullname, ignore))
                continue

            item = Items.find_or_create(fullname)
            if not item._content:
                if item.boxed:
                    # FIXME: remove these asserts when I'm convinced it's ok
                    assert item._size == item.member.size
                    assert item.box == box
                    if item.member.isreg():
                        assert item._content == item.box.tar.extractfile(item.member).read()
                else:
                    item.member = box.tar.getmember(fname)
                    item._size = item.member.size
                    item.box = box
                    if item.member.isreg():
                        item._content = item.box.tar.extractfile(item.member).read()

            yield (fname, item)

    def _mates(self, item, box):
        return self._boxer.split(item.name)[-1] in box.tar.getnames()

    def cmp(self, comparison):
        with contextlib.nested(opentar(comparison.pair[0].name,
                                       'r',
                                       StringIO.StringIO(comparison.pair[0].content[:])),
                               opentar(comparison.pair[1].name,
                                       'r',
                                       StringIO.StringIO(comparison.pair[1].content[:]))) as (comparison.pair[0].tar,
                                                                                              comparison.pair[1].tar):
            return Aggregator.cmp(self, comparison)


# ZipFile didn't become a context manager until 2.7.  :\.
import contextlib
@contextlib.contextmanager
def openzip(file, mode):
    """
    .. todo:: remove openzip once we move to python-2.7
    """
    zip = zipfile.ZipFile(file, mode)

    if zip.testzip():
        raise BadZipfile

    yield zip
    zip.close()

@_loggable
class ZipComparator(Aggregator):
    """
    Zip archive files are different if any of the members are different.
    """

    _boxer = _Boxer('{zip}')

    def _applies(self, thing):
        """
        """
        try:
            zipfile.ZipFile(StringIO.StringIO(thing.content[:]), 'r').close()

        except:
            return False

        return True

    def _expand(self, ignoring, box):
        """
        Yields pairs, (filename, Item), of the contents of *box*.
        """
        self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, box.name))

        for fname in box.zip.namelist():
            fullname = self._boxer.join(box.name, fname)
            ignore = ignoring(fullname)
            if ignore:
                self.logger.log(SAMES, 'Ignoring {0} cause {1}'.format(fullname, ignore))
                continue

            item = Items.find_or_create(fullname)
            if not item._content:
                if item.boxed:
                    # FIXME: remove these asserts when I'm convinced it's ok
                    assert item._size == item.member.file_size
                    assert item._content == box.zip.read(item.member)
                    assert item.box == box
                else:
                    item.member = box.zip.getinfo(fname)
                    item._size = item.member.file_size
                    item._content = box.zip.read(item.member)
                    item.box = box

            yield (fname, item)

    def _mates(self, item, box):
        return self._boxer.split(item.name)[-1] in box.zip.namelist()

    def cmp(self, comparison):
        with contextlib.nested(openzip(StringIO.StringIO(comparison.pair[0].content[:]), 'r'),
                               openzip(StringIO.StringIO(comparison.pair[1].content[:]), 'r')) as (comparison.pair[0].zip,
                                                                                                   comparison.pair[1].zip):

            if comparison.pair[0].zip.comment != comparison.pair[1].zip.comment:
                self._log_different(comparison)
                return Different

            return Aggregator.cmp(self, comparison)

@_loggable
class AMComparator(Comparator):
    """
    Automake generated Makefiles have some nondeterminisms.  They're
    the same if they're the same aside from that.  (May also need to
    make some allowance for different tool sets later.)
    """

    def _applies(self, thing):
        if not thing.name.endswith('Makefile'):
            return False # must be called 'Makefile'

        p = -1
        for i in range(5):
            p = thing.content.find('\n', p + 1, p + 132)
            if p is -1:
                return False # must have at least 5 lines no longer than 132 chars each

        return thing.content.find('generated by automake', 0, p) > -1 # must contain this phrase

    def cmp(self, comparison):
        (left, right) = [i.content[:].decode('utf8') for i in comparison.pair]

        (left, right) = [date_blot(i) for i in [left, right]]

        (left, right) = [re.sub(r'(?m)^MODVERSION = .*$', 'MODVERSION = ...', i, 0) for i in [left, right]]

        (left, right) = [re.sub(r'(?m)^BUILDINFO = .*$', 'BUILDINFO = ...', i, 0) for i in [left, right]]

        if left == right:
            self._log_same(comparison)
            return Same
        else:
            self._log_different(comparison)
            self._log_unidiffs([left, right],
                               [i.name for i in comparison.pair])
            return Different

@_loggable
class ConfigLogComparator(Comparator):
    """
    When autoconf tests fail, there's a line written to the config.log
    which exposes the name of the underlying temporary file.  Since
    the name of this temporary file changes from build to build, it
    introduces a nondeterminism.

    .. note:: I'd ignore config.log files, (and started to do exactly
       that), but it occurs to me that differences in autoconf
       configuration are quite likely to cause build differences.  So
       I've been more surgical.
    """

    def _applies(self, thing):
        if thing.name.endswith('config.log'):
            trigger = 'generated by GNU Autoconf'
        elif thing.name.endswith('config.status'):
            trigger = 'Generated by configure.'
        elif thing.name.endswith('config.h'):
            trigger = 'Generated from config.h.in by configure.'
        else:
            return False # must be named right

        p = -1
        for i in range(8):
            p = thing.content.find('\n', p + 1) # FIXME: is it worth it to bound this search?
            if p is -1:
                return False # must have at least 8 lines no longer than 132 chars each

        return thing.content.find(trigger, 0, p) > -1 # must contain this phrase

    def cmp(self, comparison):
        (left, right) = [i.content for i in comparison.pair]
        (left, right) = [re.sub(r'(?m)/cc.{6}\.([os])',
                                '/cc------.\1',
                                i,
                                0) for i in [left, right]]

        (left, right) = [re.sub(r'(?m)MODVERSION.*$',
                                'MODVERSION...',
                                i,
                                0) for i in [left, right]]

        (left, right) = [date_blot(i) for i in [left, right]]

        if left == right:
            self._log_same(comparison)
            return Same
        else:
            self._log_different(comparison)
            self._log_unidiffs([left, right],
                               [i.name for i in comparison.pair])
            return Different

@_loggable
class KernelConfComparator(Comparator):
    """
    When "make config" is run in the kernel, it generates an auto.conf
    file which includes a time stamp.  I think these files are
    important enough to merit more surgical checking.  This comparator
    blots out the 4th line.
    """

    def _applies(self, thing):
        if thing.name.endswith('auto.conf'):
            trigger = 'Automatically generated make config: don\'t edit'
        elif thing.name.endswith('autoconf.h'):
            trigger = 'Automatically generated C config: don\'t edit'
        else:
            return False # must be named right

        p = -1
        for i in range(8):
            p = thing.content.find('\n', p + 1) # FIXME: is it worth it to bound this search?
            if p is -1:
                return False # must have at least 8 lines no longer than 132 chars each

        return thing.content.find(trigger, 0, p) > -1 # must contain this phrase

    def cmp(self, comparison):
        (left, right) = [i.content[:].split('\n') for i in comparison.pair]
        del left[3]
        del right[3]

        if left == right:
            self._log_same(comparison)
            return Same
        else:
            self._log_different(comparison)
            self._log_unidiffs([left, right],
                               [i.name for i in comparison.pair])
            return Different

@_loggable
class ZipMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of a zipfile.
    """
    def _applies(self, thing):
        return thing.boxed and hasattr(thing.box, 'zip')

    def cmp(self, comparison):
        (left, right) = [i.member for i in comparison.pair]

        if (left.compress_type == right.compress_type
            and left.comment == right.comment
            #and left.extra == right.extra # differs sometimes
            and left.create_system == right.create_system
            and left.create_version == right.create_version
            and left.extract_version == right.extract_version
            and left.reserved == right.reserved
            and left.flag_bits == right.flag_bits
            and left.volume == right.volume
            and left.internal_attr == right.internal_attr
            and left.external_attr == right.external_attr):
            return False
        else:
            self._log_different(comparison)
            return Different


# ZipFile didn't become a context manager until 2.7.  :\.
import contextlib
@contextlib.contextmanager
def opengzip(file, mode):
    """
    .. todo:: remove opengzip once we move to python-3.x
    """
    gz = gzip.open(file, mode)
    yield gz
    gz.close()

@_loggable
class GzipComparator(Aggregator):
    """
    Gzip archives only have one member but the archive itself sadly
    includes a timestamp.  You can see the timestamp using "gzip -l -v".
    """

    _boxer = _Boxer('{gzip}')

    def _applies(self, thing):
        """
        """
        return thing.content[0:2] == b'\x1f\x8b'

    def _expand(self, ignoring, box):
        self.logger.log(logging.DEBUG, '{0} expands {1}'.format(self.__class__.__name__, box.name))

        fname = os.path.split(box.name)[1][:-3]

        fullname = self._boxer.join(box.name, fname)
        ignore = ignoring(fullname)
        if ignore:
            self.logger.log(SAMES, 'Ignoring {0} cause {1}'.format(fullname, ignore))
            return []

        item = Items.find_or_create(fullname)
        if not item._content:
            assert not item.boxed

            # This copy is only necessary because otherwise StringIO
            # seems to want to decode the mmap.
            sio = StringIO.StringIO(box.content[:])
            gz = gzip.GzipFile(box.name, 'rb', 9, sio)
            item._content = gz.read()
            item._size = len(item._content)
            item.box = box

        return [(fname, item)]

    def _mates(self, item, box):
        return os.path.split(box.name)[-1].startswith(self._boxer.split(item.name)[1])


@_loggable
class FailComparator(Comparator):
    """
    Used as a catchall - just return Difference
    """

    def _applies(self, thing):
        return True

    def cmp(self, comparison):
        self._log_different(comparison)
        self._log_unidiffs_comparison(comparison)

        return Different

def _findCommonSuffix(this, that):
    """
    find common trailing subpath.  return a 3-tuple consisting of the
    unique part of the arguments followed by the common part.
    """

    if not this or not that:
        return (this, that, '')

    (this_head, this_tail) = os.path.split(this)
    (that_head, that_tail) = os.path.split(that)
        
    if this_tail == that_tail:
        (x, y, z) = _findCommonSuffix(this_head, that_head)
        return (x, y, os.path.join(z, this_tail))
    else:
        return (this, that, '')

@_loggable
class BuriedPathComparator(Comparator):
    """
    Files which differ only in that they have their paths buried in them aren't really different.

    (currently unused).
    """

    def _applies(self, thing):
        return thing.isreg

    def cmp(self, comparison):
        (this, that) = comparison.pair
        (this.head, that.head, tail) = _findCommonSuffix(this.name, that.name)

        if this.content.find(bytes(this.head)) >= 0:
            (this_content, that_content) = [bytearray(t.content).replace(bytes(t.head), b'@placeholder@') for t in comparison.pair]
            if this_content == that_content:
                self._log_same(comparison)
                return Same

        self._log_indeterminate(comparison)
        return False

@_loggable
class SymlinkComparator(Comparator):
    """
    Symlinks are equal if they point to the same place.
    """

    def _applies(self, thing):
        return thing.islnk

    def cmp(self, comparison):
        (this, that) = [p.link for p in comparison.pair]

        if this == that:
            self._log_same(comparison)
            return Same

        else:
            self._log_different(comparison)
            return Different


@_loggable
class _ComparisonCommon(object):
    """
    This is a base class that holds utilities common to both
    :py:class:`Comparison` and :py:class:`ComparisonList`.  It is not
    intended to be instantiated.
 
    :param comparators: comparators to be applied
    :type comparators: list of :py:class:`Comparator`
    :param ignores: fnmatch style wild card patterns
    :type ignores: list of strings
    :param exit_asap: exit as soon as possible
    :type exit_asap: boolean
    """

    default_comparators = [
        NoSuchFileComparator(),
        InodeComparator(),
        EmptyFileComparator(),
        DirComparator(),
        ArMemberMetadataComparator(),
        BitwiseComparator(),
        SymlinkComparator(),
        #BuriedPathComparator(),
        ElfComparator(),
        ArComparator(),
        AMComparator(),
        ConfigLogComparator(),
        KernelConfComparator(),
        ZipComparator(),
        TarComparator(), # must be before GzipComparator
        GzipComparator(),
        CpioMemberMetadataComparator(),
        CpioComparator(),
        DateBlotBitwiseComparator(),
        FailComparator(),
        ]
    """
    .. todo:: use counts so we can make better guesses about which
       comparators to run first.
    """

    def __init__(self,
                 comparators=False,
                 ignores=[],
                 exit_asap=False):

        self.comparators = comparators if comparators is not False else self.default_comparators
        self.ignores = ignores
        self.exit_asap = exit_asap


    def ignoring(self, fname):
        return ignoring(self.ignores, fname)

    def cmp(self):
        self.logger.log(logging.FATAL, '{0} not implemented'.format(self.__class__.__name__))


@_loggable
class Comparison(_ComparisonCommon):
    """
    Represents a pair of objects to be compared.

    An instance of :py:class:`Comparison` comprises a pair of
    :py:class:`Item`, a list of :py:class:`Comparator`, and a method
    for applying the list of :py:class:`Comparator` to the pair of
    :py:class:`Item` and returning an answer.

    If exit_asap is true, the first difference will end the
    comparison.  If it is not true, the comparison will continue
    despite knowing that our aggregate result is that we are
    :py:class:`Different`.  This is useful for getting a complete list
    of all differences.

    exit_asap=False is like "make -k" in the sense that it reports on
    all differences rather than stopping after the first.

    .. todo:: exit_asap is not currently functional.

    :param lname: path name of the first thing, (the leftmost one)
    :type lname: string
    :param rname: path name of the second thing, (the rightmost one)
    :type rname: string
    :param comparators: list of comparators to be applied
    :type comparators: list of :py:class:`Comparator`
    :param ignores: wild card patterns of path names to be ignored
    :type ignores: list of strings
    :param exit_asap: exit as soon as possible
    :type exit_asap: boolean
    """

    @property
    def pair(self):
        """
        A 2 item list of the items to be compared

        .. todo:: this should be a tuple.
        """
        return self._pair

    @pair.setter
    def pair(self, value):
        """setter"""
        self._pair = value


    def __init__(self, lname='',
                 rname='',
                 litem=False,
                 ritem=False,
                 comparators=False,
                 ignores=[],
                 exit_asap=False):

        _ComparisonCommon.__init__(self,
                                   comparators=comparators,
                                   ignores=ignores,
                                   exit_asap=exit_asap)

        if rname and not ritem:
            ritem = Items.find_or_create(rname)

        if lname and not litem:
            litem = Items.find_or_create(lname)

        self.pair = (litem, ritem)
        self.children = []

        for item in self.pair:
            i = self.ignoring(item.name)
            if i:
                self.logger.log(logging.ERROR,
                                'Creating comparison using ignored item {0} cause {1}'.format(item.name, i))
                raise Ignoring

    def cmp(self):
        """
        Compare our pair of :py:class:`Item`.

        Run through our list of :py:class:`Comparator` calling each
        one in turn with our pair of :py:class:`Item`. Each comparator
        is expected to return either:

        any non True value, (null, False, etc)
           indicating an indeterminate result, that is, that this particular
           comparator could make no authoritative determinations and that the
           next comparator in the list should be tried

        :py:class:`Same`
           an authoritative declaration that the items are
           sufficiently alike and thus no further comparators need be
           tried

        :py:class:`Different`
           an authoritative declaration that the items are
           insufficiently alike and thus no further comparators need
           be tried.

        If no :py:class:`Comparator` returns non-null, then
        :py:exc:`IndeterminateResult` will be raised.

        .. todo:: exit_asap is not currently functional.
        """
        for comparator in self.comparators:
            if not comparator.applies(self):
                self.logger.log(logging.DEBUG,
                                'does not apply - {0}\n{1}'.format(comparator,
                                                                   pp.pformat([p.name for p in self._pair])))
                continue

            self.logger.log(logging.DEBUG,
                            'applies - {0}\n{1}'.format(comparator, pp.pformat([p.name for p in self._pair])))
            
            result = comparator.cmp(self)
            if result:
                if result == Same:
                    level = SAMES
                else:
                    level = DIFFERENCES

                self.logger.log(level, '{0} {1}'.format(result.__name__, self.__class__.__name__))
                return result

        self.logger.log(INDETERMINATES, 'indeterminate result for {0}'.format([p.name for p in self._pair]))
        raise IndeterminateResult

@_loggable
class ComparisonList(_ComparisonCommon):
    """
    Represents a pair of lists of path names to be compared - one from
    column a, one from column b, etc.

    An instance of :py:class:`ComparisonList` is very similar to a
    :py:class:`Comparison` except that instead of a pair of Items, it
    comprises a pair of lists of path names

    :param stuff: path names to be compared
    :type stuff: a (2-element) list of lists of string

    In all other ways, this class resembles :py:class:`Comparison`.
    """

    def __init__(self,
                 stuff,
                 comparators=False,
                 ignores=[],
                 exit_asap=False):
        _ComparisonCommon.__init__(self,
                                   comparators=comparators,
                                   ignores=ignores,
                                   exit_asap=exit_asap)

        self.stuff = []
        for lst in stuff:
            new_lst = []

            for fname in lst:
                cause = self.ignoring(fname)

                if cause:
                    self.logger.log(SAMES,
                                    'ignoring \'{0}\' cause \'{1}\' in {2}'.format(
                                        fname, cause, self.__class__.__name__))
                else:
                    new_lst.append(fname)

            self.stuff.append(new_lst)


    def cmp(self):
        Comparison.__doc__

        length = [len(i) for i in self.stuff]
        
        if not reduce(operator.eq, length):
            self.logger.log(DIFFERENCES,
                            'Different {0} lists are of different sizes: {1}'.format(
                                self.__class__.__name__, length))
            return Different

        result = Same
        for i in range(0, length[0]):
            c = Comparison(lname=self.stuff[0][i],
                           rname=self.stuff[1][i],
                           comparators=self.comparators,
                           ignores=self.ignores,
                           exit_asap=self.exit_asap).cmp()

            if not c:
                self.logger.log(INDETERMINATES, 'Indeterminate {0}'.format(self.__class__.__name__))
                raise IndeterminateResult

            if c is Different:
                self.logger.log(DIFFERENCES, 'Different {0}'.format(self.__class__.__name__))
                result = Different

                if self.exit_asap:
                    break

        if result is Same:
            self.logger.log(SAMES, 'Same {0}'.format(self.__class__.__name__))

        return result
