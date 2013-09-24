#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Time-stamp: <24-Sep-2013 10:28:16 PDT by rich@noir.com>

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

import os
import platform

import distribute_setup
distribute_setup.use_setuptools()

import setuptools
#import rcmp

__docformat__ = "restructuredtext en"

me='K Richard Pixley'
memail='rich@noir.com'

lzma = False

install_requires = [
    'arpy',
    'bz2file',
    'cpiofile',
    'elffile',
]

if lzma:
    install_requires.append('backports.lzma')

setup_requirements = install_requires + [
    'nose',
    'setuptools_git',
]

version_tuple = platform.python_version_tuple()
version = platform.python_version()

if version not in [
    '3.0.1',
    '3.1.5',
    '3.3.1',
    ]:
    setup_requirements.append('setuptools_lint')

if version not in [
    '3.0.1',
    ]:
    setup_requirements.append('sphinx>=1.0.5')


setuptools.setup(
    name='rcmp',
    version='0.7',
    author=me,
    maintainer=me,
    author_email=memail,
    maintainer_email=memail,
    keywords='',
    url = 'https://github.com/rich-pixley/rcmp',
    download_url = 'https://api.github.com/repos/rich-pixley/rcmp/tarball',
    description='A flexible and extendable file and directory comparison tool.',
    license='APACHE',
    long_description='',
    setup_requires=setup_requirements,
    install_requires=install_requires,
    py_modules=['rcmp'],
    packages=setuptools.find_packages(),
    include_package_data=True,
    test_suite='nose.collector',
    scripts = [],
    provides=[
        'rcmp',
        ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Testing',
        'Topic :: Utilities',
        ],
    entry_points = {
        'console_scripts': [
            'rcmp = rcmp.main:main',
        ],
        # 'gui_scripts': [
        #     'baz = my_package_gui.start_func',
        # ]
    },
)
