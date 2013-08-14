#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Time-stamp: <14-Aug-2013 15:23:08 PDT by ericpix@eussjlx7048.sj.us.am.ericsson.se>

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
tests for rcmp.
"""

from __future__ import unicode_literals, print_function

__docformat__ = 'restructuredtext en'

import abc
import os
import shutil
import subprocess
import tempfile
import time

import nose
from nose.tools import assert_false, assert_equal, raises

import rcmp

verbose_logging = False
if verbose_logging:
    import logging
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

def assert_isfile(filename):
    assert os.path.isfile(filename), 'missing {}'.format(filename)

rcmp_py = os.path.join('rcmp', '__init__.py')
tests_py = os.path.join('rcmp', 'tests.py')

def rmtree(dir):
    for i in range(5):
        try:
            shutil.rmtree(dir)
        except:
            print('tic {} {}'.format(i, dir))
            print(os.listdir(dir))

            if i < 4:
                time.sleep(1)
                continue
            else:
                print('clunk! {}\n'.format(dir))
                raise
        else:
            break


class testBasics(object):
    nosuch = 'nosuchfileordirectory'

    exit_asap = True

    def __init__(self):
        self.testfilenames = [rcmp_py, tests_py]
        self.itestfiles = [rcmp.Items.find_or_create(f, rcmp.root) for f in self.testfilenames]

    def setUp(self):
        rcmp.Items.reset()

    def tearDown(self):
        rcmp.Items.reset()

    @raises(rcmp.IndeterminateResult)
    def testEmpty(self):
        rcmp.Comparison(lname=self.testfilenames[0], rname=self.testfilenames[0], comparators=[], exit_asap=self.exit_asap).cmp()

    @raises(rcmp.IndeterminateResult)
    def testMissing(self):
        rcmp.Comparison(lname=self.testfilenames[0], rname=self.nosuch, comparators=[], exit_asap=self.exit_asap).cmp()

    @raises(rcmp.IndeterminateResult)
    def testEmptyList(self):
        rcmp.ComparisonList([[self.testfilenames[0]], [self.testfilenames[0]]], comparators=[], exit_asap=self.exit_asap).cmp()

    def testNoSuchRight(self):
        assert_equal(rcmp.Comparison(lname=self.testfilenames[0], rname=self.nosuch, comparators=[
            rcmp.NoSuchFileComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Different)

    def testNoSuchLeft(self):
        assert_equal(rcmp.Comparison(lname=self.nosuch, rname=self.testfilenames[0], comparators=[
            rcmp.NoSuchFileComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Different)

    def testNoSuchBoth(self):
        assert_equal(rcmp.Comparison(lname=self.nosuch, rname=self.nosuch, comparators=[
            rcmp.NoSuchFileComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    @raises(rcmp.IndeterminateResult)
    def testNoSuchNeither(self):
        assert_false(rcmp.Comparison(lname=self.testfilenames[0], rname=self.testfilenames[0], comparators=[
            rcmp.NoSuchFileComparator,
            ], exit_asap=self.exit_asap).cmp())

    def testInode(self):
        assert_equal(rcmp.Comparison(lname=self.testfilenames[0], rname=self.testfilenames[0], comparators=[
            rcmp.InodeComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testInodeList(self):
        assert_equal(rcmp.ComparisonList([[self.testfilenames[0]], [self.testfilenames[0]]], comparators=[
            rcmp.InodeComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    @raises(rcmp.IndeterminateResult)
    def testInodeIndeterminate(self):
        assert_equal(rcmp.Comparison(lname=self.testfilenames[0], rname=self.testfilenames[1], comparators=[
            rcmp.InodeComparator,
            ], exit_asap=self.exit_asap).cmp(), False)

    @raises(rcmp.IndeterminateResult)
    def testInodeIndeterminateList(self):
        assert_equal(rcmp.ComparisonList([[self.testfilenames[0]], [self.testfilenames[1]]], comparators=[
            rcmp.InodeComparator,
            ], exit_asap=self.exit_asap).cmp(), False)

    def testBitwise(self):
        assert_equal(rcmp.Comparison(lname=self.testfilenames[0], rname=self.testfilenames[0], comparators=[
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testBitwiseList(self):
        assert_equal(rcmp.ComparisonList([[self.testfilenames[0]], [self.testfilenames[0]]], comparators=[
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    @raises(rcmp.IndeterminateResult)
    def testBitwiseIndeterminate(self):
        assert_equal(rcmp.Comparison(lname=self.testfilenames[0], rname=self.testfilenames[1], comparators=[
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap).cmp(), False)

    @raises(rcmp.IndeterminateResult)
    def testBitwiseIndeterminateList(self):
        assert_equal(rcmp.ComparisonList([[self.testfilenames[0]], [self.testfilenames[1]]], comparators=[
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap).cmp(), False)

    def testElf(self):
        lname = os.path.join('testfiles', 'left', 'main.o')
        rname = os.path.join('testfiles', 'right', 'main.o')
        assert_isfile(lname)
        assert_isfile(rname)
        assert_equal(rcmp.Comparison(lname=lname,
                                     rname=rname,
                                     comparators=[
        				rcmp.ElfComparator,
                                     ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

class testBasicsSlow(testBasics):
    exit_asap = False

class testDirDirect(object):
    emptydirname = 'emptydir'
    dirnotemptybase = 'notempty'
    foilername = 'foiler'

    exit_asap = True

    def setUp(self):
        rcmp.Items.reset()
        os.makedirs(self.emptydirname)
        os.makedirs(os.path.join(self.dirnotemptybase, self.foilername))

    def tearDown(self):
        rcmp.Items.reset()
        rmtree(self.emptydirname)
        rmtree(self.dirnotemptybase)

    def testDirDirect(self):
        itestdir = rcmp.Items.find_or_create(self.emptydirname, rcmp.root)
        itestdir2 = rcmp.Items.find_or_create(self.dirnotemptybase, rcmp.root)

        ## DirComparator no longer instantiates so we don't have any
        ## easy way to stub out lower level comparators just now.

        # assert_equal(rcmp.Comparison(litem=itestdir, ritem=itestdir, comparators=[
        #     rcmp.DirComparator([]),
        #     ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

        # assert_equal(rcmp.ComparisonList([[self.emptydirname], [self.emptydirname]], comparators=[
        #     rcmp.DirComparator([]),
        #     ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

        assert_equal(rcmp.Comparison(litem=itestdir, ritem=itestdir, comparators=[
            rcmp.DirComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

        assert_equal(rcmp.ComparisonList([[self.emptydirname], [self.emptydirname]], comparators=[
            rcmp.DirComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

        assert_equal(rcmp.Comparison(litem=itestdir, ritem=itestdir2, comparators=[
            rcmp.DirComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Different)

        assert_equal(rcmp.ComparisonList([[self.emptydirname], [self.dirnotemptybase]], comparators=[
            rcmp.DirComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Different)

        assert_equal(rcmp.ComparisonList([[self.emptydirname], [self.dirnotemptybase]], comparators=[
            rcmp.DirComparator,
            ], ignores=rcmp.fntore(['*' + self.foilername]), exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testReal(self):
        itestdir = rcmp.Items.find_or_create(self.emptydirname, rcmp.root)

        r = rcmp.Comparison(litem=itestdir, ritem=itestdir, exit_asap=self.exit_asap)
        assert_equal(r.cmp(), rcmp.Same)

class testDirDirectSlow(testDirDirect):
    exit_asap = False

class TreeBase(object):
    exit_asap = True

    def setUp(self):
        rcmp.Items.reset()
        self.tdir = tempfile.mkdtemp()
        self.dirs = [os.path.join(self.tdir, dir) for dir in ['red', 'blue']]

        dirs2 = [os.path.join(p, q) for p in self.dirs for q in ['ham', 'eggs', 'spam', 'sam',
                                                            'I', 'am', 'do', 'not',
                                                            'like']]

        for dir in self.dirs + dirs2:
            os.makedirs(dir)

            for filename in ['foo', 'bar', 'baz', 'bim',
                             'george', 'fred', 'carol', 'ted',
                             'alice']:
                with open(os.path.join(dir, filename), 'wb') as f:
                    print(filename, file=f)

    def tearDown(self):
        rcmp.Items.reset()
        rmtree(self.tdir)

class testTree(TreeBase):
    def testCase1(self):
        assert_equal(rcmp.Comparison(lname=self.dirs[0], rname=self.dirs[1], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testFallThrough(self):
        r = rcmp.Comparison(lname=os.path.join(self.dirs[0], 'ham', 'foo'),
                            rname=os.path.join(self.dirs[1], 'eggs', 'bar'),
                            exit_asap=self.exit_asap)
        assert_equal(r.cmp(), rcmp.Different)

class testTreeSlow(testTree):
    exit_asap = False

class testTreeAux(TreeBase):
    def setUp(self):
        rcmp.Items.reset()
        TreeBase.setUp(self)

        for dir in self.dirs:
            filename = os.path.abspath(os.path.join(dir, 'ham', 'foo.pyc'))
            with open(filename, 'wb') as f:
                print(filename, file=f)

    def testBuried(self):
        assert_equal(rcmp.Comparison(lname=os.path.join(self.dirs[0], 'ham', 'foo.pyc'),
                                     rname=os.path.join(self.dirs[1], 'ham', 'foo.pyc'),
                                     comparators=[
            				rcmp.BuriedPathComparator,
                                        ],
                                     exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testIgnore(self):
        assert_equal(rcmp.Comparison(lname=self.dirs[0], rname=self.dirs[1], ignores=rcmp.fntore(['*.pyc']),
                                     exit_asap=self.exit_asap).cmp(),
                     rcmp.Same)

class testTreeAuxSlow(testTreeAux):
    exit_asap = False

class testSymlinks(TreeBase):
    def setUp(self):
        rcmp.Items.reset()
        TreeBase.setUp(self)

        self.red_sausage = os.path.join(self.dirs[0], 'sausage')
        self.red_bacon = os.path.join(self.dirs[0], 'bacon')
        self.red_bird = os.path.join(self.dirs[0], 'bird')

        self.blue_sausage = os.path.join(self.dirs[1], 'sausage')
        self.blue_bacon = os.path.join(self.dirs[1], 'bacon')
        self.blue_bird = os.path.join(self.dirs[1], 'bird')

        os.symlink('foo', self.red_bird)
        os.symlink('nonexistent', self.red_sausage)
        os.symlink('ham', self.red_bacon)

        os.symlink('foo', self.blue_bird)
        os.symlink('nonexistent', self.blue_sausage)
        os.symlink('ham', self.blue_bacon)

    def testBird(self):
        assert_equal(rcmp.Comparison(lname=self.red_bird, rname=self.blue_bird, exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testBacon(self):
        assert_equal(rcmp.Comparison(lname=self.red_bacon, rname=self.blue_bacon, exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testSausage(self):
        assert_equal(rcmp.Comparison(lname=self.red_sausage, rname=self.blue_sausage, exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testDir(self):
        assert_equal(rcmp.Comparison(lname=self.dirs[0], rname=self.dirs[1], exit_asap=self.exit_asap).cmp(), rcmp.Same)

class testSymlinksSlow(testSymlinks):
    exit_asap = False

class FakeComparator(rcmp.Comparator):
    """
    Raise IndeterminateResult for files named 'ham' and return Different
    for others.
    """
    @staticmethod
    def _applies(thing):
        return True

    @classmethod
    def cmp(self, comparison):
        if comparison.pair[0].name.endswith('bar'):
            raise rcmp.IndeterminateResult

        return rcmp.Different

class testSlow(TreeBase):
    def setUp(self):
        rcmp.Items.reset()
        TreeBase.setUp(self)

        with open(os.path.join(self.dirs[0], 'I', 'alice'), 'w') as fff:
            print('ho', file=fff)
            print('ho', file=fff)
            print('ho', file=fff)

    def testShort(self):
        assert_equal(rcmp.Comparison(lname=self.dirs[0], rname=self.dirs[1], comparators=[
            rcmp.DirComparator,
            FakeComparator,
            ], exit_asap=True).cmp(), rcmp.Different)

    @raises(rcmp.IndeterminateResult)
    def testLong(self):
        rcmp.Comparison(lname=self.dirs[0], rname=self.dirs[1], comparators=[
            rcmp.DirComparator,
            FakeComparator,
        ], exit_asap=False).cmp()

class testCommonSuffix(object):
    def testSimple(self):
        assert_equal(rcmp._findCommonSuffix('a/b/c', 'a/b/c'), ('', '', 'a/b/c'))
        assert_equal(rcmp._findCommonSuffix('a/b/c', 'd/e/f'), ('a/b/c', 'd/e/f', ''))
        assert_equal(rcmp._findCommonSuffix('b/a', 'c/a'), ('b', 'c', 'a'))
        assert_equal(rcmp._findCommonSuffix('a/b/c', 'd/e/c'), ('a/b', 'd/e', 'c'))
        assert_equal(rcmp._findCommonSuffix('a/b/c/d', 'e/f/c/d'), ('a/b', 'e/f', 'c/d'))
        assert_equal(rcmp._findCommonSuffix('a/b/c/d', 'e/f/g/d'), ('a/b/c', 'e/f/g', 'd'))
        assert_equal(rcmp._findCommonSuffix('a/b/c/d', 'e/b/c/d'), ('a', 'e', 'b/c/d'))

class testAr(object):
    empty = 'empty.a'
    first = 'first.a'
    second = 'second.a'
    third = 'third.a'
    left = os.path.join('testfiles', 'left', 'archive.a')
    assert_isfile(left)
    right = os.path.join('testfiles', 'right', 'archive.a')
    assert_isfile(right)

    exit_asap = True

    def setUp(self):
        rcmp.Items.reset()
        with open(self.empty, 'wb') as f:
            f.write('!<arch>\n')

        subprocess.check_call(['ar', 'cr', self.first, rcmp_py])
        subprocess.check_call(['ar', 'cr', self.second, rcmp_py])
        subprocess.check_call(['ar', 'cr', self.third, rcmp_py, tests_py])

    def tearDown(self):
        rcmp.Items.reset()
        for i in [self.empty, self.first, self.second, self.third]:
            os.remove(i)

    def testEmpty(self):
        assert_equal(rcmp.Comparison(lname=self.empty, rname=self.empty, comparators=[
            rcmp.ArMemberMetadataComparator,
            rcmp.ArComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testIdentical(self):
        r = rcmp.Comparison(lname=self.first, rname=self.first, comparators=[
            rcmp.ArMemberMetadataComparator,
            rcmp.ArComparator,
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap)
        assert_equal(r.cmp(), rcmp.Same)

    def testTwo(self):
        assert_equal(rcmp.Comparison(lname=self.first, rname=self.second, comparators=[
            rcmp.ArMemberMetadataComparator,
            rcmp.ArComparator,
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Same)

    def testDifferent(self):
        assert_equal(rcmp.Comparison(lname=self.first, rname=self.third, comparators=[
            rcmp.ArMemberMetadataComparator,
            rcmp.ArComparator,
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Different)

    def testOtherDifferent(self):
        assert_equal(rcmp.Comparison(lname=self.third, rname=self.first, comparators=[
            rcmp.ArMemberMetadataComparator,
            rcmp.ArComparator,
            rcmp.BitwiseComparator,
            ], exit_asap=self.exit_asap).cmp(), rcmp.Different)

    def testArElf(self):
        r = rcmp.Comparison(lname=self.left, rname=self.right, comparators=[
            rcmp.ArMemberMetadataComparator,
            rcmp.ArComparator,
            rcmp.ElfComparator,
            ], exit_asap=self.exit_asap)
        assert_equal(r.cmp(), rcmp.Same)

class testArSlow(testAr):
    exit_asap = False

class SimpleAbstract(object):
    __metaclass__ = abc.ABCMeta

    exit_asap = True

    @abc.abstractproperty
    def filenames(self):
        return None

    @abc.abstractproperty
    def comparators(self):
        return []

    sides = ['left', 'right']

    def __init__(self, exit_asap=True):
        (self.lefts, self.rights) = [[os.path.join('testfiles', side, filename) for filename in self.filenames]
                                     for side in self.sides]
        for f in self.lefts + self.rights:
            assert_isfile(f)

        self.exit_asap = exit_asap

    def testIdentical(self):
        for left in self.lefts:
            r = rcmp.Comparison(lname=left, rname=left, comparators=self.comparators, exit_asap=self.exit_asap)
            assert_equal(r.cmp(), rcmp.Same)

    def testOne(self):
        for left, right in zip(self.lefts, self.rights):
            r = rcmp.Comparison(lname=left, rname=right, comparators=self.comparators, exit_asap=self.exit_asap)
            assert_equal(r.cmp(), rcmp.Same)

    def testReal(self):
        for left, right in zip(self.lefts, self.rights):
            r = rcmp.Comparison(lname=left, rname=right, exit_asap=self.exit_asap)
            assert_equal(r.cmp(), rcmp.Same)

    @raises(rcmp.IndeterminateResult)
    def testBad(self):
        for left in self.lefts:
            r = rcmp.Comparison(lname=left, rname='/dev/null', comparators=self.comparators, exit_asap=self.exit_asap)
            assert_equal(r.cmp(), rcmp.Different)

class testEmpty(SimpleAbstract):
    filenames = ['empty']

    comparators = [
        rcmp.EmptyFileComparator,
    ]

class testEmptySlow(testEmpty):
    exit_asap = False

class testAr2(SimpleAbstract):
    filenames = ['archive.a']

    comparators = [
        rcmp.BitwiseComparator,
        rcmp.ArMemberMetadataComparator,
        rcmp.ArComparator,
    ]

    def setUp(self):
        rcmp.Items.reset()
        for side in ['left', 'right']:
            fname = os.path.join('testfiles', side, 'stumper')

            try:
                os.remove(fname)
            except:
                pass

            with open(fname, 'wb'):
                pass
            os.chmod(fname, 0)

    def tearDown(self):
        rcmp.Items.reset()
        for side in ['left', 'right']:
            try:
                os.remove(os.path.join('testfiles', side, 'stumper'))

            except OSError, val:
                if val is 2:
                    pass
                else:
                    raise

class testAr2Slow(testAr2):
    exit_asap = False

class testAM(SimpleAbstract):
    filenames = ['Makefile']
    comparators = [rcmp.AMComparator]

class testConfigLog(SimpleAbstract):
    # don't know what these were.  :(.
    not_filenames = ['2config.log', 'db-config.log', '3config.log' ]
    filenames = ['config.log', 'config.status' ]
    comparators = [rcmp.ConfigLogComparator]

# FIXME: need some kernel conf files.
# class testKernelConf(SimpleAbstract):
#     filenames = ['auto.conf', 'autoconf.h']
#     comparators = [rcmp.KernelConfComparator]

class testGzip(SimpleAbstract):
    filenames = ['Makefile.in.gz', 'yo.gz.gz.gz']
    comparators = [rcmp.GzipComparator, rcmp.BitwiseComparator]

class testZip(SimpleAbstract):
    #filenames = ['jarfile.jar', 'tst_unzip_file.zip', 'third.zip']
    filenames = ['zipfile.zip']
    comparators = [
        rcmp.ZipMemberMetadataComparator,
        rcmp.ZipComparator,
        rcmp.BitwiseComparator,
        ]

    testdir = 'testfiles'
    nullfilename = 'nullfile.zip'
    emptyfilename = 'emptyfile.zip'
    fnames = []

    def __init__(self):
        self.fnames = []
        SimpleAbstract.__init__(self)

    def setUp(self):
        rcmp.Items.reset()
        for fname in [os.path.join(self.testdir, side, self.nullfilename) for side in ['left', 'right']]:
            self.fnames.append(fname)
            with open(fname, 'wb'):
                pass

        for fname in [os.path.join(self.testdir, side, self.emptyfilename) for side in ['left', 'right']]:
            self.fnames.append(fname)
            with rcmp.openzip(fname, 'w') as f:
                pass

    def tearDown(self):
        rcmp.Items.reset()
        for fname in self.fnames:
            os.remove(fname)

# FIXME: need some test files
# class testDateBlot(SimpleAbstract):
#     filenames = ['icu-config', 'acinclude.m4', 'compile.h']
#     comparators = [rcmp.DateBlotBitwiseComparator]

class testCpio(SimpleAbstract):
    filenames = ['cpiofile.cpio']
    comparators = [
        rcmp.BitwiseComparator,
        rcmp.SymlinkComparator,
        rcmp.CpioMemberMetadataComparator,
        rcmp.CpioComparator,
        ]

class testTar(SimpleAbstract):
    filenames = ['tarfile.tar']
    comparators = [
        rcmp.BitwiseComparator,
        rcmp.SymlinkComparator,
        rcmp.TarMemberMetadataComparator,
        rcmp.TarComparator,
        ]

class testScript(object):
    def testHelp(self):
        with open('/dev/null', 'w') as devnull:
            assert_equal(subprocess.call('rcmp --help'.split(), stdout=devnull, stderr=devnull), 0)

    def testBasic(self):
        assert_equal(subprocess.call('rcmp testfiles/left testfiles/left'.split()), 0)

    def testFail(self):
        assert_equal(subprocess.call('rcmp testfiles/main.c testfiles/configure.ac'.split()), 1)

    def testBasicv(self):
        assert_equal(subprocess.call('rcmp -v testfiles/left testfiles/right'.split()), 0)

    def testBasicRead(self):
        assert_equal(subprocess.call('rcmp --read testfiles/left testfiles/right'.split()), 0)

    def testBasicMmap(self):
        assert_equal(subprocess.call('rcmp --mmap testfiles/left testfiles/right'.split()), 0)

    def testIgnores(self):
        ignorefile = 'ignorefile'

        with open(ignorefile, 'w') as fileobj:
            fileobj.write('*main.c\n*configure.ac\n')

        with open('/dev/null', 'w') as devnull:
            assert_equal(subprocess.call('rcmp -i {} testfiles/main.c testfiles/configure.ac'.format(ignorefile).split(),
                                         stdout=devnull, stderr=devnull), 1)
        os.remove(ignorefile)
    

# def testNew():
#     assert_equal(rcmp.Comparison(lname='testfiles/left/libpulse_0.9.22-6_opal.ipk',
#                                  rname='testfiles/right/libpulse_0.9.22-6_opal.ipk',
#                                  ignores=rcmp.fntore(['*/temp']), exit_asap=self.exit_asap).cmp(),
#                  rcmp.Same)

if __name__ == '__main__':
    nose.main()
