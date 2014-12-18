#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-

'''
Qubes OS

:copyright: © 2010-2014 Invisible Things Lab
'''

__author__ = 'Invisible Things Lab'
__license__ = 'GPLv2 or later'
__version__ = 'R3'

import os
import sys
import re
import argparse

HEADER = '''\
# vim: set syntax=yaml ts=4 sw=4 sts=4 et :
#
# Use this file to assist adding words to dictionary.
# ===================================================
#
# Delete any lines with misspelt words.
# Keep lines with correctly missspelt words.
# Save file and run spelling-tool add <this_file> <master spelling list>
#
'''


def main(argv):
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="subparser", help='commands')

    # Missing spelling parser
    missing_parser = subparsers.add_parser(
        'missing',
        help='Parse missing words for editing',
        description='Parses spelling output file to assist in adding missing words to dictionary')
    missing_parser.add_argument(
        'input_filename',
        action="store",
        help="Input spelling text filename")

    add_parser = subparsers.add_parser(
        'add',
        help='Add words to dictionary',
        description='Parses words missing yaml file and adds all words to master dictionary')
    add_parser.add_argument(
        'input_filename',
        action="store",
        help="Input missing words text yaml filename")
    add_parser.add_argument(
        'output_filename',
        action="store",
        help="Output master dictionary text filename")

    args = parser.parse_args()

    if args.subparser == 'missing':
        missing(args.input_filename)
    elif args.subparser == 'add':
        add(args.input_filename, args.output_filename)


def add(input_filename, output_filename):
    dictionary = set()

    regex = (r'''
        ^(?!\#)(?P<word>^\s*.*):   # word
    ''')

    with open(input_filename, "rb") as infile:
        for line in infile.readlines():
            line = line.rstrip('\r\n')

            matches = re.match(regex, line, re.VERBOSE)
            if not matches:
                continue
            dictionary.add(matches.group('word').strip())

    with open(output_filename, "rb") as infile:
        for line in infile.readlines():
            line = line.rstrip('\r\n')
            dictionary.add(line.strip())

    with open(output_filename, "wb") as outfile:
        for word in sorted(dictionary):
            outfile.write(word + '\n')


def missing(input_filename):
    # Store the words in dictionary; no duplicates
    dictionary = {}

    dirname = os.path.dirname(input_filename)
    basename = os.path.splitext(os.path.basename(input_filename))[0]
    output_filename = '{0}/{1}-missing.yaml'.format(dirname, basename)

    regex = (r'''
        (?P<filename>.*?):       # filename
        (?P<line>.*?):           # line number
        .*?\((?P<word>.*)\)[ ]   # word
        (?P<replacements>\[.*)$  # suggested replacement words
    ''')

    with open(input_filename, "rb") as infile, open(output_filename,
                                                    "wb") as outfile:
        for line in infile.readlines():
            line = line.rstrip('\r\n')

            matches = re.match(regex, line, re.VERBOSE)
            if not matches:
                continue

            dictionary[matches.group('word')] = matches

        if dictionary:
            outfile.writelines(HEADER)

            for word, matches in sorted(dictionary.items()):
                group = 'word'
                line = '{0:18}  : {1}'.format(
                    word,
                    matches.group('replacements').strip())
                print line
                outfile.write(line + '\n')


if __name__ == "__main__":
    main(sys.argv[1:])


def setup_spellingtool(app, exception):
    if hasattr(app.builder, 'output_filename'):
        missing(app.builder.output_filename)


def setup(app):
    app.connect('build-finished', setup_spellingtool)
