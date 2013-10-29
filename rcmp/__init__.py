#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Time-stamp: <29-Oct-2013 15:59:20 PDT by rich@noir.com>

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

.. autoclass:: Box
   :members:

.. autoclass:: Comparison
   :members:

.. autoclass:: ComparisonList
   :members:

Comparators
===========

..fixme:: comparators should probably be zero instance strategies.

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
.. autoclass:: Bz2Comparator
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
    'Box',
    'Comparison',
    'ComparisonList',
    'rootItem',

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
    'Bz2Comparator',
    'CpioMemberMetadataComparator',
    'CpioComparator',
    'DateBlotBitwiseComparator',
    'FailComparator',
]

lzma = False

import abc

if lzma:
    import backports.lzma as lzma

import bz2file as bz2
import contextlib
import difflib
import errno
import fnmatch
import gzip
import io
import logging
import mmap
import operator
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import elffile
import arpy
import cpiofile

DIFFERENCES = logging.WARNING
SAMES = logging.WARNING - 1
INDETERMINATES = logging.WARNING - 2

#logging.basicConfig(style='{')

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
    cls.logger = logging.getLogger('{}.{}'.format(__name__, cls.__name__))
    return cls


_read_count = 3

@_loggable
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

    def __init__(self, name, parent, box=None):
        assert parent

        self._name = name
        self._statbuf = False
        self._fd = False
        self._content = False
        self._link = False
        self._size = None
        self._read_count = 0
        self._native = False

        self.parent = parent
        self._box = box if box else DirComparator

        self.logger.log(logging.DEBUG,
                        'Item(name = %s, parent = %s, box = %s)', name,
                        parent.name if hasattr(parent, 'name') else 'None',
                        self._box.__name__)

    @property
    def box(self):
        return self._box

    @box.setter
    def box(self, value):
        """setter"""
        assert value
        self._box = value

    @property
    def name(self):
        """
        name in the extended file system name space of this :py:class:`Item`.

        :rtype: string
        """
        return self._name

    @property
    def shortname(self):
        return self.box.member_shortname(self)

    @property
    def content(self):
        """
        The contents of the entire file, in memory.

        :rtype: bytearray.
        """

        global _read_count

        try:

            if self._content is False:
                self._content = self.parent.box.member_content(self)
                self._read_count += 1
                if self._read_count > _read_count:
                    _read_count = self._read_count

        except TypeError:
            self.logger.log(logging.ERROR, 'self = %s, %s', self, self.name)
            self.logger.log(logging.ERROR, 'self.parent = %s, %s', self.parent, self.parent.name)
            self.logger.log(logging.ERROR, 'self.box = %s', self.box)
            self.logger.log(logging.ERROR, 'self.box.member_content = %s', self.box.member_content)

            self.logger.log(logging.ERROR, 'self.parent.box = %s, %s', self.parent.box, self.parent.box.__name__)
            self.logger.log(logging.ERROR, 'self.parent.box.member_content = %s', self.parent.box.member_content)
            raise

        return self._content

    def reset(self):
        self.logger.log(logging.DEBUG, 'resetting %s', self.name)
        self._content = False

    @property
    def stat(self):
        """
        If we have a statbuf, return it.

        If not, then look one up, cache it, and return it.

        :rtype: statbuf
        """
        if not self._statbuf:
            self._statbuf = self.parent.box.member_stat(self)

        return self._statbuf

    @property
    def exists(self):
        """
        Check for existence.

        :rtype: boolean
        """
        try:
            return self.parent.box.member_exists(self)

        except:
            self.logger.log(logging.DEBUG, 'self = %s, self.box = %s', self, self.box)
            raise

    @property
    def inode(self):
        """
        Return the inode number from stat.

        :rtype: string
        """
        return self.box.member_inode(self)

    @property
    def device(self):
        """
        Return device number from stat.

        :rtype: string
        """
        return self.box.member_device(self)

    @property
    def size(self):
        """
        Return our size.  Look it up in stat, (and cache the result), if
        we don't already know what it is.

        :rtype: int
        """
        if self._size is None:
            self._size = self.parent.box.member_size(self)

        return self._size

    @property
    def isdir(self):
        """
        Return True if and only if we are represent a file system
        directory.

        :rtype: boolean
        """
        try:
            return self.parent.box.member_isdir(self)

        except:
            self.logger.log(logging.DEBUG, 'isdir self = %s, self.box = %s', self.name, self.box)
            raise

    @property
    def isreg(self):
        """
        Return True if and only if we represent a regular file.

        :rtype: boolean
        """
        return self.parent.box.member_isreg(self)

    @property
    def islnk(self):
        """
        Return True if and only if we represent a symbolic link.

        :rtype: boolean
        """
        return self.parent.box.member_islnk(self)

    @property
    def link(self):
        """
        Return a string representing the path to which the symbolic link
        points.  This presumes that we are a symbolic link.

        :rtype: string
        """
        if not self._link:
            self._link = self.parent.box.member_link(self)

        return self._link


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
    def find_or_create(cls, name, parent, box=None):
        """
        Look up an :py:class:`Item` with *name*.  If necessary, create it.

        :param name: the name of the :py:class`Item` to look up
        :type name: string
        :rtype: :py:class:`Item`
        """
        if not box:
            box = DirComparator

        ### FIXME: I suspect this is extraneous.  It breaks zipfiles
        ### with foo/.  Remove it once it's settled.
        # name = os.path.abspath(name)
        if name in cls._content:
            return cls._content[name]
        else:
            x = Item(name, parent, box)
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

    @classmethod
    def reset(cls):
        cls._content = {}

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
    subclasses.  It is never instantiated. (lie - fixme).

    Subclasses based on :py:class:`Comparator` implement individual
    heuristics for comparing items when applied to a
    :py:class:`Comparison`.  There are many :py:class:`Comparator`
    subclasses included.

    ..note:: :py:class:`Comparator`s are strategies.  That is, there are no
             instantiation variables nor properties.
    """
    __metaclass__ = abc.ABCMeta

    @staticmethod
    @abc.abstractmethod
    def _applies(thing):
        return False

    @classmethod
    def applies(cls, comparison):
        """
        Return True if and only if we apply to the given comparison.

        :type comparison: :py:class:`Comparison`
        :rtype: boolean
        """
        return reduce(operator.iand, [cls._applies(i) for i in comparison.pair])

    @classmethod
    @abc.abstractmethod
    def cmp(cls, comparison):
        """
        Apply ourselves to the given :py:class:`Comparison`.

        If can make an authoritative determination about whether the
        :py:class:`Items` are alike then return either
        :py:class:`Same` or :py:class:`Different`.  If we can make no
        such determination, then return a non-True value.

        :type comparison: :py:class:`Comparison`
        :rtype: :py:class:`Same`, :py:class:`Different`, or a non-True value
        """
        cls.logger.error('%s.cmp() isn\'t overridden.', cls.__name__)

        raise NotImplementedError
        return False

    @classmethod
    def _log_item(cls, item):
        if item.exists and item.islnk:
            return (item.name, item.link)
        else:
            return item.name

    @classmethod
    def _log_string(cls, s, comparison):
        return '{0} {1} {2}'.format(s, cls.__name__, comparison.pair[0].name.partition(os.sep)[2])

    @classmethod
    def _log_unidiffs(cls, content, names):
        try:
            cls.logger.log(DIFFERENCES,
                            '\n'.join(difflib.unified_diff(content[0].split('\n'),
                                                           content[1].split('\n'),
                                                           names[0], names[1],
                                                           '', '', 3, '')))
        except UnicodeError:
            pass

    @classmethod
    def _log_unidiffs_comparison(cls, comparison):
        cls._log_unidiffs([i.content for i in comparison.pair],
                           [i.name for i in comparison.pair])

    @classmethod
    def _log_different(cls, comparison):
        cls.logger.log(DIFFERENCES, cls._log_string('Different', comparison))

    @classmethod
    def _log_same(cls, comparison):
        cls.logger.log(SAMES, cls._log_string('Same', comparison))

    @classmethod
    def _log_indeterminate(cls, comparison):
        cls.logger.log(INDETERMINATES, cls._log_string('Indeterminate', comparison))


class DatePattern(object):
    def __init__(self, pattern, replacement):
        self.pattern = pattern
        self.replacement = replacement
        self.compiled = re.compile(pattern)

dow = r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat)'
moy = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
lmoy = r'(January|February|March|April|May|June|July|August|September|October|November|December)'

date_patterns = [
    # Sun Feb 13 12:29:28 PST 2011
    DatePattern(dow + r' ' + moy + r' *[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} (PST|PDT) [0-9]{4}',
     'Day Mon 00 00:00:00 LOC 2011'),
    
    DatePattern(dow + r' ' + moy + r' *[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}',
     'Day Mon 00 00:00:00 2011'),

    # 13 FEB 2011 11:52
    DatePattern(r'(?i) *[0-9]{1,2} (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC) [0-9]{4} [0-9]{2}:[0-9]{2}',
     '00 MON 2011 00:00'),

    # "April  7, 2011"
    DatePattern(lmoy + r' *[0-9]{1,2}\\?, [0-9]{4}', 'Month 00, 2011'),

    # Wed Apr 13 2011
    DatePattern(dow + r' ' + moy + r' *[0-9]{1,2} *[0-9]{4}', 'Day Mon 00 2011'),

    # Wed 13 Apr 2011
    DatePattern(dow + r' *[0-9]{1,2} *' + moy + r' *[0-9]{4}', 'Day 00 Mon 2011'),

    # Wed 13 April 2011
    DatePattern(dow + r' *[0-9]{1,2} *' + lmoy + r' *[0-9]{4}', 'Day 00 Month 2011'),

    # 2011-04-13
    DatePattern(r'20*[0-9]{2}-*[0-9]{2}-*[0-9]{2}', '2011-00-00'),

    # Apr 2011
    DatePattern(moy + r' [0-9]{4}', 'Mon 2011'),

    # 00:00:00
    DatePattern(r'[0-9]{2}:[0-9]{2}:[0-9]{2}', '00:00:00'),

    # 2011-07-11T170033Z
    DatePattern(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z', '00000000T000000Z'),
    ]

def date_blot(input_string):
    """Convert dates embedded in a string into innocuous constants of uniform length.
    
    :param input_string: input string
    :rtype: string
    """
    retval = input_string

    for pat in date_patterns:
        try:
            retval = pat.compiled.sub(pat.replacement, retval)

        except UnicodeError:
            pass

    return retval

# def ignoring(ignores, fname):
#     """
#     Given a list of file names to be ignored and a specific file name
#     to check, return the first ignore pattern from the list that
#     matches the file name.

#     :param ignores: ignore patterns
#     :type ignores: list of strings
#     :param fname: file name to check
#     :type fname: string
#     :rtype: string or False (Can be used as a predicate.)
#     """
#     for ignore in ignores:
#         if fnmatch.fnmatch(fname, ignore):
#             return ignore

#     return False

def fntore(names):
    """
    Convert a list of wildcard style patterns into a list of compiled regexps.
    """
    return [re.compile(fnmatch.translate(n)) for n in names]

def fntoreconcat(names):
    """
    Convert a list of wildcard style patterns into a list of compiled regexps.
    """
    return [re.compile('|'.join([fnmatch.translate(n) for n in names]))]

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
        try:
            if ignore.match(fname):
                return ignore

        except AttributeError:
            logger.log(logging.ERROR, 'ignore = %s', ignore)
            raise

    return False

@_loggable
class InodeComparator(Comparator):
    """
    Objects with the same inode and device are identical.
    """

    @classmethod
    def _applies(cls, item):
        return item.box is DirComparator

    @classmethod
    def cmp(cls, comparison):
        if (reduce(operator.eq, [i.inode for i in comparison.pair])
            and reduce(operator.eq, [i.device for i in comparison.pair])):
            cls._log_same(comparison)
            return Same
        else:
            cls._log_indeterminate(comparison)
            return False

@_loggable
class EmptyFileComparator(Comparator):
    """
    Two files which are each empty are equal.  In particular, we don't
    need to open them or read them to make this determination.
    """

    @classmethod
    def _applies(cls, item):
        return item.isreg

    @classmethod
    def cmp(cls, comparison):
        if (comparison.pair[0].size == 0
            and comparison.pair[1].size == 0):
            cls._log_same(comparison)
            return Same
        else:
            cls._log_indeterminate(comparison)
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

class _Packer(object):
    """
    just for aggregation, not intended for instantiation.
    """

    def __init__(self, joiner='/'):
        self.joiner = joiner

    def join(self, left, right):
        return '{0}{1}{2}'.format(left, self.joiner, right)

    def split(self, path):
        return path.split(self.joiner)

class Box(Comparator):
    """
    This is an abstract base class intended for comparators on things
    which are composed of other things.  So, for instance, a
    directory, or a file archive.

    ..note:: subclasses are strategies - they have no properties.
    """
    __metaclass__ = abc.ABCMeta

    # : An instance of :py:class:_Packer: to use for path manipulation.
    _packer = None

    @classmethod
    def member_shortname(cls, member):
        return cls._packer.split(member.name)[-1]

    @staticmethod
    @abc.abstractmethod
    def _applies(thing):
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def box_keys(cls, item):
        raise NotImplementedError

    @classmethod
    def _no_mate(cls, name, logger):
        cls.logger.log(DIFFERENCES, 'Different %s No mate: %s', cls.__name__, name)

    @classmethod
    def _expand(cls, ignoring, item):
        for shortname in cls.box_keys(item):
            fullname = cls._packer.join(item.name, shortname)
            ignore = ignoring(fullname)
            if ignore:
                cls.logger.log(SAMES, 'Ignoring %s cause %s', fullname, ignore)
                continue

            newitem = Items.find_or_create(fullname, item, cls)

            cls.logger.log(logging.DEBUG, '%s expands %s -> %s', cls.__name__, item.name, shortname)
            yield (shortname, newitem)

    @staticmethod
    def _mates(item, container):
        #Box.logger.log(logging.DEBUG, '_mates: item = %s, container = %s', item.name, container.name)
        return item.shortname in container.box.box_keys(container)

    @classmethod
    def _outer_join(cls, comparison, invert=False, spool=True):
        # left outer join
        result = False

        if invert:
            rparent, lparent = [p for p in comparison.pair]
        else:
            lparent, rparent = [p for p in comparison.pair]

        for shortname, litem in cls._expand(comparison.ignoring, lparent):
            rname = cls._packer.join(rparent.name, shortname)
            ignore = comparison.ignoring(litem.name)
            if ignore:
                cls.logger.log(SAMES, 'Ignoring %s cause %s', lname, ignore)
                continue

            ritem = Items.find_or_create(rname, rparent, cls)
            if cls._mates(litem, rparent):
                if spool:
                    cls.logger.log(logging.DEBUG, 'spooling %s', litem.name)
                    comparison.children.append(Comparison(litem=litem,
                                                          ritem=ritem,
                                                          comparators=comparison.comparators,
                                                          ignores=comparison.ignores,
                                                          exit_asap=comparison.exit_asap,
                                                          ignore_ownerships=comparison.ignore_ownerships))
            else:
                cls._no_mate(litem.name, logger)
                result = Different

        return result

    @classmethod
    def _left_outer_join(cls, comparison):
        return cls._outer_join(comparison)

    @classmethod
    def _right_outer_join(cls, comparison):
        # we should already have a comparison for this
        # pair but I'd need to rearrange the ordering to
        # do an assert to prove it.
        return cls._outer_join(comparison, invert=True, spool=False)

    @classmethod
    def _inner_join(cls, comparison):
        # inner join
        retval = Same
        for c in comparison.children:
            r = c.cmp()

            if not r:
                cls._log_indeterminate(comparison)
                raise IndeterminateResult

            if r == Different:
                cls._log_different(comparison)
                retval = Different
                if comparison.exit_asap:
                    return retval

        return retval

    @classmethod
    def cmp(cls, comparison):
        """
        Compare our lists and return the result.
        """
        cls.logger.log(logging.DEBUG, 'Box.cmp(%s, ...', cls.__name__)

        retval = Same
        comparison.pair[0].box = comparison.pair[1].box = cls

        if (cls._left_outer_join(comparison) == Different
            or cls._right_outer_join(comparison) == Different):
            # already logged earlier
            retval = Different
            if comparison.exit_asap:
                comparison.reset()
                return retval

        if cls._inner_join(comparison) == Different:
            # already logged earlier
            retval = Different
            if comparison.exit_asap:
                comparison.reset()
                return retval

        if retval == Same:
            cls._log_same(comparison)
            comparison.reset()

        return retval

    @staticmethod
    @abc.abstractmethod
    def member_content(member):
        raise NotImplementedError

    @staticmethod
    def member_stat(member):
        """
        If member has a statbuf, return it.

        If not, then look one up, cache it, and return it.

        :rtype: statbuf
        """
        raise NotImplementedError

    @staticmethod
    def member_exists(member):
        """
        Check for existence.

        :rtype: boolean
        """
        Box.logger.log(logging.DEBUG, 'member_exists: member = %s, parent.box(%s) -> %s', member.name,
                                                                                               member.parent.name,
                                                                                               member.parent.box.box_keys(member.parent))
        return member.shortname in member.parent.box.box_keys(member.parent)

    @staticmethod
    def member_inode(member):
        """
        Return the inode number from stat.

        :rtype: string
        """
        Box.logger.log(logging.ERROR, 'member_inode not implemented for %s', member.name)
        raise NotImplementedError

    @staticmethod
    def member_device(member):
        """
        Return device number from stat.

        :rtype: string
        """
        Box.logger.log(logging.ERROR, 'member_device not implemented for %s', member.name)
        raise NotImplementedError

    @staticmethod
    def member_size(member):
        """
        Return our size.

        :rtype: int
        """
        Box.logger.log(logging.ERROR, 'member_size not implemented for %s', member.name)
        raise NotImplementedError

    @staticmethod
    def member_isdir(member):
        """
        Return True if and only if we are represent a directory.

        So far, none of the archive formats recur.  That is, they're
        all flat collections of files rather than being collections of
        collections necessarily.  Although such can be created, they
        aren't an inherent part of the file format.

        :rtype: boolean
        """
        Box.logger.log(logging.ERROR, 'member_isdir not implemented for %s', member.name)
        raise NotImplementedError

    @staticmethod
    def member_isreg(member):
        """
        Return True if and only if member represents a regular file.

        :rtype: boolean
        """
        Box.logger.log(logging.ERROR, 'member_isreg not implemented for %s', member.name)
        raise NotImplementedError

    @staticmethod
    def member_islnk(member):
        """
        Return True if and only if we represent a symbolic link.

        :rtype: boolean
        """
        Box.logger.log(logging.ERROR, 'member_islnk not implemented for %s', member.name)
        raise NotImplementedError

    @staticmethod
    def member_link(member):
        """
        Return a string representing the path to which the symbolic link
        points.  This presumes that we are a symbolic link.

        :rtype: string
        """
        Box.logger.log(logging.ERROR, 'member_link not implemented for %s', member.name)
        raise NotImplementedError


class ContentOnlyBox(Box):
    """
    Some containers like zip and gzip only have members with actual
    content.  That is, no symlinks, no devices, etc.
    """

    @staticmethod
    def member_isreg(member):
        return True

    @staticmethod
    def member_isdir(member):
        return False

    @staticmethod
    def member_islnk(member):
        return False

class UnixBox(Box):
    """
    Archivers like tar and cpio are capable of tracking hard and soft
    links as well as devices, directories and ownerships, etc.
    """

    @staticmethod
    def member_isdir(member):
        return False


@_loggable
class DirComparator(Box):
    """
    Objects which are directories are special.  They match if their
    contents match.

    .. fixme: this could be a box too.
    """

    _packer = _Packer('/')

    @staticmethod
    def _applies(item):
        return item.isdir

    @classmethod
    def box_keys(cls, item):
        if not hasattr(item, 'dirs'):
            item.dirs = os.listdir(item.name)

        return item.dirs

    @staticmethod
    @contextlib.contextmanager
    def member_mmap(member):
        with open(member.name, 'rb') as fd:
            yield mmap.mmap(fd.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ)
            fd.close()

    @staticmethod
    def member_content(member):
        with open(member.name, 'rb') as fd:
            return fd.read()

    @staticmethod
    def member_exists(member):
        """
        Check for existence.

        :rtype: boolean
        """
        return os.path.exists(member.name)

    @staticmethod
    def member_stat(member):
        """
        :rtype: statbuf
        """
        return os.lstat(member.name)

    @staticmethod
    def member_inode(member):
        """
        Return the inode number from stat.

        :rtype: string
        """
        return member.stat.st_ino

    @staticmethod
    def member_device(member):
        """
        Return device number from stat.

        :rtype: string
        """
        return member.stat.st_dev

    @staticmethod
    def member_size(member):
        """
        Return our size.

        :rtype: int
        """
        return member.stat.st_size

    @staticmethod
    def member_isdir(member):
        """
        Return True if and only if we are represent a file system
        directory.

        :rtype: boolean
        """
        return stat.S_ISDIR(member.stat.st_mode)

    @staticmethod
    def member_isreg(member):
        """
        Return True if and only if we represent a regular file.

        :rtype: boolean
        """
        return stat.S_ISREG(member.stat.st_mode)

    @staticmethod
    def member_islnk(member):
        """
        Return True if and only if we represent a symbolic link.

        :rtype: boolean
        """
        return stat.S_ISLNK(member.stat.st_mode)

    @staticmethod
    def member_link(member):
        """
        Return a string representing the path to which the symbolic link
        points.  This presumes that we are a symbolic link.

        :rtype: string
        """
        return os.readlink(member.name)


@_loggable
class BitwiseComparator(Comparator):
    """
    Objects which are bitwise identical are close enough.
    """

    @staticmethod
    def _applies(item):
        BitwiseComparator.logger.log(logging.DEBUG, 'testing whether BitwiseComparator applies to %s', item.name)
        return item.isreg

    @classmethod
    def cmp(cls, comparison):
        # if they're not the same size, then they're not bitwise identical.

        if not reduce(operator.eq, [i.size for i in comparison.pair]):
            cls._log_indeterminate(comparison)
            return False

        # If we already have their content mapped, or they aren't file
        # system files, then use content.  If they're the same, then
        # we can drop the content because we won't need it again.

        if (reduce(operator.eq, [bool(i._content) for i in comparison.pair] + [True])
             or comparison.pair[0].parent.box != DirComparator):
            if comparison.pair[0].content == comparison.pair[1].content:
                comparison.reset()
                cls._log_same(comparison)
                return Same

            else:
                cls._log_indeterminate(comparison)
                return False

        # at this point we know that a) we are regular files in file
        # system files and b) neither one yet has _content.

        # This is clumsy but the vast majority of file comparisons
        # turn out to be Same on BitwiseComparator.  And I was sorry
        # to lose the mmap earlier so I'm putting it back in here.

        # Mmap both files.  Compare.  If they're the same, we're done
        # with these files.  If they're not the same, then copy their
        # contents out of mmap into _content.

        with contextlib.nested(DirComparator.member_mmap(comparison.pair[0]),
                               DirComparator.member_mmap(comparison.pair[1])) as (m1, m2):
            if m1 == m2:
                cls._log_same(comparison)
                return Same

            else:
                comparison.pair[0]._content = m1[:]
                comparison.pair[1]._content = m2[:]

                cls._log_indeterminate(comparison)
                retval = False

        return retval


@_loggable
class DateBlotBitwiseComparator(Comparator):
    """
    Objects which are bitwise identical after date blotting are close
    enough.  But this should only be tried late.
    """

    @staticmethod
    def _applies(item):
        return item.isreg

    @classmethod
    def cmp(cls, comparison):
        if (reduce(operator.eq, [date_blot(i.content) for i in comparison.pair])):
            cls._log_same(comparison)
            retval = Same
        else:
            cls._log_indeterminate(comparison)
            retval = False

        return retval


@_loggable
class NoSuchFileComparator(Comparator):
    """
    Objects are different if either one is missing.
    """
    # FIXME: perhaps this should return same if both are missing.

    @staticmethod
    def _applies(item):
        return True

    @classmethod
    def cmp(cls, comparison):
        e = [i.exists for i in comparison.pair]
        if reduce(operator.ne, e):
            cls._log_different(comparison)
            return Different

        if e[0] is False:
            cls._log_same(comparison)
            return Same

        cls._log_indeterminate(comparison)
        return False

@_loggable
class ElfComparator(Comparator):
    """
    Elf files are different if any of the important sections are
    different.
    """

    _magic = b'\x7fELF'

    @staticmethod
    def _applies(item):
        return item.content.find(ElfComparator._magic, 0, len(ElfComparator._magic)) == 0

    @classmethod
    def cmp(cls, comparison):
        e = [(i.content.find(cls._magic, 0, len(cls._magic)) == 0) for i in comparison.pair]
        if not reduce(operator.iand, e):
            cls._log_different(comparison)
            return Different

        e = [elffile.open(name=i.name, block=i.content) for i in comparison.pair]
        if e[0].close_enough(e[1]):
            cls._log_same(comparison)
            return Same
        else:
            cls._log_different(comparison)

            with tempfile.NamedTemporaryFile(delete=False) as left:
                leftname = left.name
                left.write(comparison.pair[0].content)

            lcontent = subprocess.check_output(str('objdump -sfh {}'.format(leftname)).split())
            os.remove(leftname)

            with tempfile.NamedTemporaryFile(delete=False) as right:
                rightname = right.name
                right.write(comparison.pair[1].content)

            rcontent = subprocess.check_output(str('objdump -sfh {}'.format(rightname)).split())
            os.remove(rightname)

            cls._log_unidiffs([lcontent, rcontent], [i.name for i in comparison.pair])
            return Different

@_loggable
class ArMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of an ar archive.
    """
    @staticmethod
    def _applies(item):
        return (item.parent is not None) and (item.parent.box is ArComparator)

    @classmethod
    def cmp(cls, comparison):
        cls.logger.log(logging.DEBUG, 'cmp: pair[0] = %s', comparison.pair[0].name)
        cls.logger.log(logging.DEBUG, 'cmp: parent = %s', comparison.pair[0].parent.name)

        (left, right) = [i.parent.ar.archived_files[i.shortname].header for i in comparison.pair]

        if ((comparison.ignore_ownerships
             or (left.uid == right.uid
                 and left.gid == right.gid))
            and left.mode == right.mode):
            return False
        else:
            cls._log_different(comparison)
            diffmsg = ''

            if left.uid != right.uid:
                diffmsg += '\n uid = {} {}'.format(left.uid, right.uid)

            if left.gid != right.gid:
                diffmsg += '\n gid = {} {}'.format(left.gid, right.gid)

            if left.mode != right.mode:
                diffmsg += '\nmode = {} {}'.format(left.mode, right.mode)

            diffmsg += '\n\n'
            cls.logger.log(DIFFERENCES, diffmsg)
            return Different


@contextlib.contextmanager
def openar(filename, fileobj):
    """
    """
    ar = arpy.Archive(filename=filename, fileobj=fileobj)
    ar.read_all_headers()
    yield ar
    ar.close()

# its possible that ar can hold directories or devices.  It has a
# "mode" field.  But in practice, this doesn't seem to be used.

@_loggable
class ArComparator(ContentOnlyBox):
    """
    Ar archive files are different if any of the important members are
    different.

    .. note:: This is a strategy - there are no instance
       properties. Rather, the content is stored in the comparison
       pairs.
    """

    _magic = b'!<arch>\n'

    _packer = _Packer('{ar}')

    @staticmethod
    def _applies(item):
        return item.content.find(ArComparator._magic, 0, len(ArComparator._magic)) == 0

    @classmethod
    def box_keys(cls, item):
        cls.logger.log(logging.DEBUG, '%s.box_keys(%s) -> %s', cls.__name__,
                                                                     item.name,
                                                                     item.ar.archived_files.keys())
        return item.ar.archived_files.keys()

    @staticmethod
    def member_size(member):
        return member.parent.ar.archived_files[member.shortname].header.size

    @staticmethod
    def member_content(member):
        return member.parent.ar.archived_files[member.shortname].read()

    @classmethod
    def cmp(cls, comparison):
        with contextlib.nested(openar(comparison.pair[0].name,
                                      io.BytesIO(comparison.pair[0].content)),
                               openar(comparison.pair[1].name,
                                      io.BytesIO(comparison.pair[1].content))) as (comparison.pair[0].ar,
                                                                                   comparison.pair[1].ar):
            return super(cls, cls).cmp(comparison)


@_loggable
class CpioMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of a cpio archive.
    """
    @staticmethod
    def _applies(item):
        return item.parent.box is CpioComparator

    @classmethod
    def cmp(cls, comparison):
        (left, right) = [i.parent.cpio.get_member(i.shortname) for i in comparison.pair]

        if (left.mode == right.mode
            and (comparison.ignore_ownerships
                 or (left.uid == right.uid
                     and left.gid == right.gid))
            and left.rdevmajor == right.rdevmajor
            and left.rdevminor == right.rdevminor
            and left.filesize == right.filesize):

            # if the file has no content then we can say conclusively
            # that they are the same at this point.
            if left.filesize == 0:
                return Same
            else:
                return False
        else:
            cls._log_different(comparison)
            diffmsg = ''

            if left.uid != right.uid:
                diffmsg += '\n uid = {} {}'.format(left.uid, right.uid)

            if left.gid != right.gid:
                diffmsg += '\n gid = {} {}'.format(left.gid, right.gid)

            if left.rdevmajor != right.rdevmajor:
                diffmsg += '\nrdevmajor = {} {}'.format(left.rdevmajor, right.rdevmajor)

            if left.rdevminor != right.rdevminor:
                diffmsg += '\nrdevminor = {} {}'.format(left.rdevminor, right.rdevminor)

            if left.filesize != right.filesize:
                diffmsg += '\nfilesize = {} {}'.format(left.filesize, right.filesize)

            diffmsg += '\n\n'
            cls.logger.log(DIFFERENCES, diffmsg)
            return Different


@contextlib.contextmanager
def opencpio(filename, guts):
    """
    """
    cpio = cpiofile.CpioFile().open(name=filename, block=guts)
    yield cpio
    cpio.close()

@_loggable
class CpioComparator(UnixBox):
    """
    Cpio archive files are different if any of the important members
    are different.

    .. note:: This is a strategy - there are no instance
       properties. Rather, the content is stored in the comparison
       pairs.
    """

    _packer = _Packer('{cpio}')

    @staticmethod
    def _applies(item):
        return bool(cpiofile.valid_magic(item.content))

    @classmethod
    def box_keys(cls, item):
        return item.cpio.names

    @staticmethod
    def member_size(member):
        return member.parent.cpio.get_member(member.shortname).filesize

    @staticmethod
    def member_content(member):
        return member.parent.cpio.get_member(member.shortname).content

    @staticmethod
    def member_isreg(member):
        return stat.S_ISREG(member.parent.cpio.get_member(member.shortname).mode)

    @staticmethod
    def member_islnk(member):
        return stat.S_ISLNK(member.parent.cpio.get_member(member.shortname).mode)

    @staticmethod
    def member_link(member):
        return member.content

    @classmethod
    def cmp(cls, comparison):
        with contextlib.nested(opencpio(comparison.pair[0].name, comparison.pair[0].content),
                               opencpio(comparison.pair[1].name, comparison.pair[0].content)) as (comparison.pair[0].cpio,
                                                                                                     comparison.pair[1].cpio):
            return super(cls, cls).cmp(comparison)


@_loggable
class TarMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of an ar archive.
    """
    @staticmethod
    def _applies(item):
        return item.parent.box is TarComparator

    @classmethod
    def cmp(cls, comparison):
        (left, right) = [i.parent.box.getmember(i) for i in comparison.pair]

        if (left.mode == right.mode
            and left.type == right.type
            and left.linkname == right.linkname
            and (comparison.ignore_ownerships
                 or (left.uid == right.uid
                     and left.gid == right.gid
                     and left.uname == right.uname
                     and left.gname == right.gname))):

            # if the file has no content then we can say conclusively
            # that they are the same at this point.
            if left.size == 0:
                return Same
            else:
                return False
        else:
            cls._log_different(comparison)
            diffmsg = ''

            if left.mode != right.mode:
                diffmsg += '\n mode = {} {}'.format(left.mode, right.mode)

            if left.type != right.type:
                diffmsg += '\n type = {} {}'.format(left.type, right.type)

            if left.linkname != right.linkname:
                diffmsg += '\n linkname = {} {}'.format(left.linkname, right.linkname)

            if left.uid != right.uid:
                diffmsg += '\n uid = {} {}'.format(left.uid, right.uid)

            if left.gid != right.gid:
                diffmsg += '\n gid = {} {}'.format(left.gid, right.gid)

            if left.uname != right.uname:
                diffmsg += '\nuname = {} {}'.format(left.uname, right.uname)

            if left.gname != right.gname:
                diffmsg += '\ngname = {} {}'.format(left.gname, right.gname)

            diffmsg += '\n\n'
            cls.logger.log(DIFFERENCES, diffmsg)
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
class TarComparator(UnixBox):
    """
    Tar archive files are different if any of the important members
    are different.

    .. note:: must be called *after* GzipComparator in order to duck
       the Python tarfile module's pathological performace with compressed
       archives.

    .. note:: This is a strategy - there are no instance
       properties. Rather, the content is stored in the comparison
       pairs.
    """

    _packer = _Packer('{tar}')

    @staticmethod
    def _applies(item):
        # NOTE: this doesn't catch old style tar archives but if we're
        # lucky, we won't need to.

        try:
            tarfile.open(fileobj=io.BytesIO(item.content)).close()

        except:
            return False

        return True

        #return (item.content.find('ustar', 257, 264) > -1)
                
    @staticmethod
    def getmember(item):
        if not hasattr(item, 'member'):
            item.member = item.parent.tar.getmember(item.shortname)

        return item.member

    @classmethod
    def box_keys(cls, item):
        if not hasattr(item, 'names'):
            item.names = item.tar.getnames()

        return item.names

    @staticmethod
    def member_size(member):
        return member.parent.box.getmember(member).size

    @staticmethod
    def member_content(member):
        info = member.parent.box.getmember(member)
        assert info

        if info.isdir() or info.isdev():
            return ''

        fileobj = member.parent.tar.extractfile(member.shortname)
        if not fileobj:
            TarComparator.logger.log(logging.ERROR, 'member_content could not find %s, (%s), in %s', member.shortname,
                                                                                                           member.name,
                                                                                                           member.parent.name)
            raise NotImplementedError
        return fileobj.read()

    @staticmethod
    def member_isreg(member):
        return member.parent.box.getmember(member).isreg()

    @staticmethod
    def member_islnk(member):
        return member.parent.box.getmember(member).issym()

    @staticmethod
    def member_link(member):
        return member.parent.box.getmember(member).linkname

    @classmethod
    def cmp(cls, comparison):
        with contextlib.nested(opentar(comparison.pair[0].name, 'r',
                                       io.BytesIO(comparison.pair[0].content)),
                               opentar(comparison.pair[1].name,
                                       'r',
                                       io.BytesIO(comparison.pair[1].content))) as (comparison.pair[0].tar,
                                                                                    comparison.pair[1].tar):
            return super(cls, cls).cmp(comparison)


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
class ZipComparator(ContentOnlyBox):
    """
    Zip archive files are different if any of the members are different.

    .. note:: This is a strategy - there are no instance
       properties. Rather, the content is stored in the comparison
       pairs.
    """

    _myname = 'zip'

    _packer = _Packer('{{}}'.format(_myname))

    @staticmethod
    def _applies(item):
        """
        """
        try:
            zipfile.ZipFile(io.BytesIO(item.content), 'r').close()

        except:
            return False

        return True

    @classmethod
    def box_keys(cls, item):
        return item.zip.namelist()

    @staticmethod
    def member_size(member):
        return member.parent.zip.getinfo(member.shortname).file_size

    @staticmethod
    def member_content(member):
        return member.parent.zip.read(member.shortname)

    @classmethod
    def cmp(cls, comparison):
        with contextlib.nested(openzip(io.BytesIO(comparison.pair[0].content), 'r'),
                               openzip(io.BytesIO(comparison.pair[1].content), 'r')) as (comparison.pair[0].zip,
                                                                                         comparison.pair[1].zip):

            if comparison.pair[0].zip.comment != comparison.pair[1].zip.comment:
                cls._log_different(comparison)
                return Different

            return super(cls, cls).cmp(comparison)

@_loggable
class AMComparator(Comparator):
    """
    Automake generated Makefiles have some nondeterminisms.  They're
    the same if they're the same aside from that.  (May also need to
    make some allowance for different tool sets later.)
    """

    @staticmethod
    def _applies(item):
        if not item.name.endswith('Makefile'):
            return False # must be called 'Makefile'

        p = -1
        for i in range(5):
            p = item.content.find('\n', p + 1, p + 132)
            if p is -1:
                return False # must have at least 5 lines no longer than 132 chars each

        return item.content.find('generated by automake', 0, p) > -1 # must contain this phrase

    @classmethod
    def cmp(cls, comparison):
        (left, right) = [i.content.decode('utf8') for i in comparison.pair]

        (left, right) = [date_blot(i) for i in [left, right]]

        (left, right) = [re.sub(r'(?m)^MODVERSION = .*$', 'MODVERSION = ...', i, 0) for i in [left, right]]

        (left, right) = [re.sub(r'(?m)^BUILDINFO = .*$', 'BUILDINFO = ...', i, 0) for i in [left, right]]

        if left == right:
            cls._log_same(comparison)
            return Same
        else:
            cls._log_different(comparison)
            cls._log_unidiffs([left, right],
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

    @staticmethod
    def _applies(item):
        if item.name.endswith('config.log'):
            trigger = 'generated by GNU Autoconf'
        elif item.name.endswith('config.status'):
            trigger = 'Generated by configure.'
        elif item.name.endswith('config.h'):
            trigger = 'Generated from config.h.in by configure.'
        else:
            return False # must be named right

        p = -1
        for i in range(8):
            p = item.content.find('\n', p + 1) # FIXME: is it worth it to bound this search?
            if p is -1:
                return False # must have at least 8 lines no longer than 132 chars each

        return item.content.find(trigger, 0, p) > -1 # must contain this phrase

    @classmethod
    def cmp(cls, comparison):
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
            cls._log_same(comparison)
            return Same
        else:
            cls._log_different(comparison)
            cls._log_unidiffs([left, right],
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

    @staticmethod
    def _applies(item):
        if item.name.endswith('auto.conf'):
            trigger = 'Automatically generated make config: don\'t edit'
        elif item.name.endswith('autoconf.h'):
            trigger = 'Automatically generated C config: don\'t edit'
        else:
            return False # must be named right

        p = -1
        for i in range(8):
            p = item.content.find('\n', p + 1) # FIXME: is it worth it to bound this search?
            if p is -1:
                return False # must have at least 8 lines no longer than 132 chars each

        return item.content.find(trigger, 0, p) > -1 # must contain this phrase

    @classmethod
    def cmp(cls, comparison):
        (left, right) = [i.content.split('\n') for i in comparison.pair]
        del left[3]
        del right[3]

        if left == right:
            cls._log_same(comparison)
            return Same
        else:
            cls._log_different(comparison)
            cls._log_unidiffs([left, right],
                               [i.name for i in comparison.pair])
            return Different

@_loggable
class ZipMemberMetadataComparator(Comparator):
    """
    Verify the metadata of each member of a zipfile.
    """
    @staticmethod
    def _applies(item):
        return item.box is ZipComparator

    @classmethod
    def cmp(cls, comparison):
        (left, right) = [i.parent.zip.getinfo(i.shortname) for i in comparison.pair]

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
            cls._log_different(comparison)
            diffmsg = ''

            if left.compress_type != right.compress_type:
                diffmsg += '\n compress_type = {} {}'.format(left.compress_type, right.compress_type)

            if left.comment != right.comment:
                diffmsg += '\n comment = {} {}'.format(left.comment, right.comment)

            if left.create_system != right.create_system:
                diffmsg += '\ncreate_system = {} {}'.format(left.create_system, right.create_system)

            if left.create_version != right.create_version:
                diffmsg += '\ncreate_version = {} {}'.format(left.create_version, right.create_version)

            if left.extract_version != right.extract_version:
                diffmsg += '\nextract_version = {} {}'.format(left.extract_version, right.extract_version)

            if left.reserved != right.reserved:
                diffmsg += '\nreserved = {} {}'.format(left.reserved, right.reserved)

            if left.flag_bits != right.flag_bits:
                diffmsg += '\nflag_bits = {} {}'.format(left.flag_bits, right.flag_bits)

            if left.volume != right.volume:
                diffmsg += '\nvolume = {} {}'.format(left.volume, right.volume)

            if left.internal_attr != right.internal_attr:
                diffmsg += '\ninternal_attr = {} {}'.format(left.internal_attr, right.internal_attr)

            if left.external_attr != right.external_attr:
                diffmsg += '\nexternal_attr = {} {}'.format(left.external_attr, right.external_attr)

            diffmsg += '\n\n'
            cls.logger.log(DIFFERENCES, diffmsg)
            return Different


class Encoder(ContentOnlyBox):
    """
    Most UN*X compression programs compress a single stream of data.
    Similarly, many encryption programs do the same.
    """
    __metaclass__ = abc.ABCMeta

    # : 
    _content_name = None

    @staticmethod
    @abc.abstractmethod
    def open(filename, mode, fileobj):
        raise NotImplementedError

    @classmethod
    def box_keys(cls, item):
        return [cls._content_name]

    @staticmethod
    def member_size(member):
        return len(member.content)

    @classmethod
    def cmp(cls, comparison):
        for p in comparison.pair:
            p.box = cls

        return Comparison(litem=Item(cls._packer.join(comparison.pair[0].name, cls._content_name),
                                     comparison.pair[0],
                                     box=cls),
                          ritem=Item(cls._packer.join(comparison.pair[1].name, cls._content_name),
                                     comparison.pair[1],
                                     box=cls),
                          comparators=comparison.comparators,
                          ignores=comparison.ignores,
                          exit_asap=comparison.exit_asap,
                          ignore_ownerships=comparison.ignore_ownerships).cmp()

@_loggable
class GzipComparator(Encoder):
    """
    Gzip archives only have one member but the archive itself sadly
    includes a timestamp.  You can see the timestamp using "gzip -l -v".
    """

    _myname = 'gzip'

    _packer = _Packer('{{{}}}'.format(_myname))

    _content_name = '{{{}content}}'.format(_myname)

    @staticmethod
    @contextlib.contextmanager
    def open(filename, mode, fileobj):
        # GzipFile didn't become a context manager until 2.7.  :\.
        gz = gzip.GzipFile(filename, mode, 9, fileobj)
        yield gz
        gz.close()

    @staticmethod
    def _applies(item):
        return bytes(item.content[0:2]) == b'\x1f\x8b'

    @staticmethod
    def member_content(member):
        with GzipComparator.open(member.parent.name, 'rb', io.BytesIO(member.parent.content)) as gzipobj:
            return gzipobj.read()


@_loggable
class BZ2Comparator(Encoder):
    """
    BZ2 archives only have one member.
    """

    _myname = 'bz2'

    _packer = _Packer('{{{}}}'.format(_myname))

    _content_name = '{{{}content}}'.format(_myname)

    # BZ2File didn't become a context manager until 2.7.  :\.
    @staticmethod
    @contextlib.contextmanager
    def open(filename, mode, fileobj):
        """
        .. todo:: remove openzip once we drop python-2.6
        """
        bobj = bz2.BZ2File(fileobj if fileobj else filename, mode, None, 9)
        yield bobj
        bobj.close()

    @staticmethod
    def _applies(item):
        return bytes(item.content[0:2]) == b'BZ'

    @staticmethod
    def member_content(member):
        with BZ2Comparator.open(member.parent.name, 'rb', io.BytesIO(member.parent.content)) as bz2obj:
            return bz2obj.read()

@_loggable
class XZComparator(Encoder):
    """
    XZ archives only have one member.
    """

    _myname = 'xz'

    _packer = _Packer('{{{}}}'.format(_myname))

    _content_name = '{{{}content}}'.format(_myname)

    @staticmethod
    @contextlib.contextmanager
    def open(filename, mode, fileobj):
        xzobj = lzma.LZMAFile(fileobj if fileobj else filename, mode)
        yield xzobj
        xzobj.close()

    @staticmethod
    def _applies(item):
        """
        ..note:: lzma format files have no magic number.  So while the lzma
                 library can open them, we don't really have a way to recognize
                 them easily other than just attempting to open and living with
                 failures.  But that seems pretty expensive and besides, who
                 uses lzma?
        """
        return bytes(item.content[0:6]) == b'\xfd7zXZ\x00'

    @staticmethod
    def member_content(member):
        with XZComparator.open(member.parent.name, 'rb', io.BytesIO(member.parent.content)) as xzobj:
            return xzobj.read()

@_loggable
class FailComparator(Comparator):
    """
    Used as a catchall - just return Difference
    """

    @staticmethod
    def _applies(item):
        return True

    @classmethod
    def cmp(cls, comparison):
        cls._log_different(comparison)
        cls.logger.log(DIFFERENCES, '\n')
        cls._log_unidiffs_comparison(comparison)

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

    @staticmethod
    def _applies(item):
        return item.isreg

    @classmethod
    def cmp(cls, comparison):
        (this, that) = comparison.pair
        (this.head, that.head, tail) = _findCommonSuffix(this.name, that.name)

        if this.content.find(bytes(this.head)) >= 0:
            (this_content, that_content) = [bytearray(t.content).replace(bytes(t.head), b'@placeholder@') for t in comparison.pair]
            if this_content == that_content:
                cls._log_same(comparison)
                return Same

        cls._log_indeterminate(comparison)
        return False

@_loggable
class SymlinkComparator(Comparator):
    """
    Symlinks are equal if they point to the same place.
    """

    @staticmethod
    def _applies(item):
        return item.islnk

    @classmethod
    def cmp(cls, comparison):
        (this, that) = [p.link for p in comparison.pair]

        if this == that:
            cls._log_same(comparison)
            return Same

        else:
            cls._log_different(comparison)
            return Different


@_loggable
class MapComparator(Comparator):
    """
    Linker map files include a reference to the output file which is
    typically a generated temp file name.
    """
    @staticmethod
    def _applies(item):
        try:
            retval = item.content.startswith('Archive member included')

        except UnicodeDecodeError:
            # must not be.
            retval = False

        return retval

    _pattern = re.compile('tmp-\d*')

    @classmethod
    def cmp(cls, comparison):
        munged = [cls._pattern.sub('tmp-0', i.content) for i in comparison.pair]
        if reduce(operator.eq, munged):
            cls._log_same(comparison)
            return Same

        else:
            cls._log_indeterminate(comparison)
            return False


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
    :param exit_asap: exit as soon as possible (Indeterminate is always raised asap)
    :type exit_asap: boolean
    :param ignore_ownerships: ignore differences in element ownerships
    :type ignore_ownerships: boolean
    """

    default_comparators = [
        NoSuchFileComparator,
        InodeComparator,
        EmptyFileComparator,
        DirComparator,
        ArMemberMetadataComparator,
        BitwiseComparator,
        SymlinkComparator,
        #BuriedPathComparator,
        ElfComparator,
        ArComparator,
        AMComparator,
        ConfigLogComparator,
        KernelConfComparator,
        #XZComparator,
        BZ2Comparator,
        GzipComparator,
        ZipComparator,
        TarMemberMetadataComparator,
        TarComparator, # must be before GzipComparator
        CpioMemberMetadataComparator,
        CpioComparator,
        MapComparator,
        DateBlotBitwiseComparator,
        FailComparator,
        ]
    """
    .. todo:: use counts so we can make better guesses about which
       comparators to run first.
    """

    def __init__(self,
                 comparators=False,
                 ignores=[],
                 exit_asap=False,
                 ignore_ownerships=False):

        self.comparators = comparators if comparators is not False else self.default_comparators
        self.ignores = ignores
        self.exit_asap = exit_asap
        self.ignore_ownerships=ignore_ownerships


    def ignoring(self, fname):
        return ignoring(self.ignores, fname)

    def cmp(self):
        self.logger.log(logging.FATAL, '%s not implemented', self.__class__.__name__)


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

    If ignore_ownerships is true, then any differences in element ownerships
    are ignored.

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
    :param ignore_ownerships: ignore differences in element ownerships
    :type ignore_ownerships: boolean
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

    def reset(self):
        self.logger.log(logging.DEBUG, 'resetting %s', self.pair[0].name)
        for item in self.pair:
            item.reset()

    def __init__(self, lname='',
                 rname='',
                 litem=False,
                 ritem=False,
                 comparators=False,
                 ignores=[],
                 exit_asap=False,
                 ignore_ownerships=False):

        _ComparisonCommon.__init__(self,
                                   comparators=comparators,
                                   ignores=ignores,
                                   exit_asap=exit_asap,
                                   ignore_ownerships=ignore_ownerships)

        if rname and not ritem:
            ritem = Items.find_or_create(rname, root, DirComparator)

        if lname and not litem:
            litem = Items.find_or_create(lname, root, DirComparator)

        self.pair = (litem, ritem)
        self.children = []

        for item in self.pair:
            i = self.ignoring(item.name)
            if i:
                self.logger.log(logging.ERROR,
                                'Creating comparison using ignored item %s cause %s', item.name, i)
                raise sys.exit(1)

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
                                'does not apply - %s %s', comparator, self._pair[0].name)
                continue

            self.logger.log(logging.DEBUG,
                            'applies - %s %s', comparator, self._pair[0].name)
            
            result = comparator.cmp(self)
            if result:
                self.logger.log(logging.DEBUG, '%s %s', result.__name__, self.__class__.__name__)
                self.reset()
                return result

        self.logger.log(INDETERMINATES, 'indeterminate result for %s', [p.name for p in self._pair])
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
                 exit_asap=False,
                 ignore_ownerships=False):
        _ComparisonCommon.__init__(self,
                                   comparators=comparators,
                                   ignores=ignores,
                                   exit_asap=exit_asap,
                                   ignore_ownerships=ignore_ownerships)

        self.stuff = []
        for lst in stuff:
            new_lst = []

            for fname in lst:
                cause = self.ignoring(fname)

                if cause:
                    self.logger.log(SAMES,
                                    'ignoring \'%s\' cause \'%s\' in %s', 
                                        fname, cause, self.__class__.__name__)
                else:
                    new_lst.append(fname)

            self.stuff.append(new_lst)


    def cmp(self):
        Comparison.__doc__

        length = [len(i) for i in self.stuff]
        
        result = Same
        if not reduce(operator.eq, length):
            self.logger.log(DIFFERENCES,
                            'Different %s lists are of different sizes: %s', 
                                self.__class__.__name__, length)
            retval = Different
            if self.exit_asap:
                return retval

        for i in range(0, max(length)):
            comparison = Comparison(litem=Items.find_or_create(self.stuff[0][i], root),
                                    ritem=Items.find_or_create(self.stuff[1][i], root),
                                    comparators=self.comparators,
                                    ignores=self.ignores,
                                    exit_asap=self.exit_asap,
                                    ignore_ownerships=self.ignore_ownerships)
            c = comparison.cmp()

            if not c:
                self.logger.log(INDETERMINATES, 'Indeterminate %s', self.__class__.__name__)
                raise IndeterminateResult
            else:
                comparison.reset()

            if c is Different:
                self.logger.log(logging.DEBUG, 'Different %s', self.__class__.__name__)
                result = Different

                if self.exit_asap:
                    return result

        if result is Same:
            self.logger.log(SAMES, 'Same %s', self.__class__.__name__)

        return result

# : this is used to parent top level Items
root = Item('{root}', True)
