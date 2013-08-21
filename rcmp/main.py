#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Time-stamp: <20-Aug-2013 19:36:15 PDT by rich@noir.com>

# Copyright © 2013 K Richard Pixley
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
Shell callable driver for the :py:mod:`rcmp` library.
"""

import argparse
import fnmatch
import logging
import os
import re

import rcmp

__docformat__ = "restructuredtext en"

def main():
    """
    Parses command line options and calls library.
    """
    logger = logging.getLogger()
    handler = logging.StreamHandler()

    options = _parse_args()

    log_level = logging.ERROR

    if options.verbose == 1:
        log_level = rcmp.DIFFERENCES
    elif options.verbose == 2:
        log_level = rcmp.SAMES
    elif options.verbose == 3:
        log_level = rcmp.INDETERMINATES
    elif options.verbose > 3:
        log_level = logging.DEBUG

    logger.setLevel(log_level)
    logger.addHandler(handler)

    ignores = []

    for ifile in options.ignorefiles:
        if os.path.isfile(ifile):
            with open(ifile, 'r') as ignorefile:
                ignores += [line.strip() for line in ignorefile]

    result = rcmp.Comparison(lname=options.left,
                             rname=options.right,
                             ignores=rcmp.fntore(ignores),
                             exit_asap=options.exit_asap).cmp()

    return 0 if result == rcmp.Same else 1

def _parse_args():
    """
    Parses the command line arguments.

    :return: Namespace with arguments.
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser(description='Recursively CoMPares two trees.')
    
    parser.add_argument('left', help='First tree to check.')
    parser.add_argument('right', help='Second tree to check.')

    parser.add_argument('-e', '--exit-asap', '--exit-early',
                        default=False, action='store_true', help='Exit on first difference. [default %(default)s]')

    defaultignorefiles = [os.path.expanduser('.rcmpignore')]
    parser.add_argument('-i', '--ignorefile', action='append', type=str, default=defaultignorefiles, dest='ignorefiles',
                        help='Read the named file as ignorefile. [default \'%(default)s\']')

    parser.add_argument('-v', '--verbose', action='count', help='Be more verbose. (can be repeated)')

    return parser.parse_args()
