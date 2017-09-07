#!/usr/bin/env python3

#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2017  Wojtek Porczyk <woju@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

'''
A simple policy fuzzer/tester
=============================

This basically generates all relevant combinations of policy rules and puts them
through policy line parser. Then sorts them according to parse result. It is
intended for reviewing changes to policy parser.

The intended use is as follows:

    1. Adjust the generation of rules to include the intended syntax change
    (e.g. new directive or whatever).
    2. Dump the results of running in master and in pull request.
    3. Compare results using standard diff tools.

Remember about PYTHONPATH when running from repo.

Further directions
------------------

    - Get some decisions from the policy, using an example system_info.

'''

# those are used as both src/dst and as values for [default_]target= param
VM = (
    '$adminvm',
    '$anyvm',
    '$default',
    '$dispvm',
    '$dispvm:vmname',
    '$dispvm:$tag:vmname',
    '$invalid',
    '$tag:mytag',
    '$type:AdminVM',
    '$type:AppVM',
    'dom0',
    'vmname',
)

ACTION = (
    'allow',
    'deny',
    'ask',
    'invalid'
)

PARAM = (
    'target',
#   'user',
    'default_target',
)

import functools
import collections
import itertools

import qubespolicy

class Rule(object):
    pass_src = set()
    pass_dest = set()
    pass_action = set()
    pass_params = collections.defaultdict(set)

    fail_src = set()
    fail_dest = set()
    fail_action = set()
    fail_params = collections.defaultdict(set)

    def __init__(self, src, dest, action, params):
        self.src = src
        self.dest = dest
        self.action = action
        self.params = tuple(pv for pv in params if pv[1] is not None)

    def mark(self, result):
        set_src, set_dest, set_action, set_params = \
            (self.pass_src, self.pass_dest, self.pass_action, self.pass_params)\
                if result else \
            (self.fail_src, self.fail_dest, self.fail_action, self.fail_params)
        set_src.add(self.src)
        set_dest.add(self.dest)
        set_action.add(self.action)
        for k, v in self.params:
            set_params[k].add(v)

    def __str__(self):
        return '{:23s} {:23s} {:15s} {}'.format(
            self.src, self.dest, self.action,
            ' '.join(map('='.join, sorted(self.params))))

    @classmethod
    def stat(cls):
        return '''\
pass_src = {}
pass_dest = {}
pass_action = {}
pass_params = {}

fail_src = {}
fail_dest = {}
fail_action = {}
fail_params = {}
'''.format(*map(sorted,
    (cls.pass_src, cls.pass_dest, cls.pass_action, cls.pass_params.items(),
        cls.fail_src, cls.fail_dest, cls.fail_action, cls.fail_params.items())))

def gen_params(param):
    return zip(itertools.repeat(param), itertools.chain((None, ''), VM))

def gen_rules():
    # XXX BEWARE of changed argument order; this is to group actions together
    for action, src, dest, params in itertools.product(ACTION, VM, VM,
            itertools.product(*map(gen_params, PARAM))):
        yield Rule(src, dest, action, params)


def main(args=None):
    for line in gen_rules():
        try:
            rule = qubespolicy.PolicyRule(str(line))
            line.mark(True)
            print('PASS: {}'.format(line))
        except qubespolicy.PolicySyntaxError as e:
            line.mark(False)
            print('FAIL: {}\n  {} {!s}'.format(line, type(e).__name__, e))
        except Exception as e:
            print('ERR!: {}\n  {} {!s}'.format(line, type(e).__name__, e))

    print()
    print(Rule.stat())

if __name__ == '__main__':
    main()
