#!/usr/bin/python2
# vim: fileencoding=utf8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010-2016  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2011-2016  Marek Marczykowski-Górecki
#                                              <marmarek@invisiblethingslab.com>
# Copyright (C) 2016       Wojtek Porczyk <woju@invisiblethingslab.com>
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
''' Shutdown a qube '''

from __future__ import print_function

import sys
import thread
import time

import qubes.config
import qubes.tools

parser = qubes.tools.QubesArgumentParser(description=__doc__, vmname_nargs='+')

parser.add_argument(
    '--force', action='store_true', default=False,
    help='force operation, even if may damage other VMs (eg. shutdown of'
    ' network provider)')

parser.add_argument('--timeout', action='store', type=float,
                    default=qubes.config.defaults['shutdown_counter_max'],
                    help='timeout after which a domain is killed (default: %d)')


def has_connected_vms(vm):
    ''' Return `True` if vm has running domains connected to it '''
    vms = [v for v in vm.connected_vms if not v.is_halted()]
    return len(vms) > 0


def children_vms(domains):
    ''' Return only domains which are not halted and have no domains connected
        to them.
    '''
    return [vm for vm in domains
            if not vm.is_halted() and not has_connected_vms(vm)]


def validate_dependencies(args):
    ''' Print errors if domains can not be shutdown because of other domains
        connected to them. Returns `False` on failure.
    '''
    domains = set(args.domains)
    error = False
    for vm in domains:
        connected_vms = set([v for v in vm.connected_vms if not v.is_halted()])
        if not domains.issuperset(connected_vms):
            error = True
            not_specified_domains = connected_vms.difference(domains)
            names = ", ".join([v.name for v in not_specified_domains])
            msg = "Can't shutdown domain '{!s}' it " \
                  "has other domains connected:" \
                   .format(vm)
            args.app.log.error(msg + " " + names)

    return not error


def shutdown(vm):
    vm.shutdown()


def main(args=None):  # pylint: disable=missing-docstring
    args = parser.parse_args(args)
    args.domains = [vm for vm in args.domains if not vm.is_halted()]
    if not validate_dependencies(args):
        return 2

    children = children_vms(args.domains)
    waiting_for_shutdown = {}

    while children:
        for vm in children_vms(args.domains):
            if vm in waiting_for_shutdown:
                start_time = waiting_for_shutdown[vm]
                if time.time() - start_time > args.timeout:
                    args.app.log.error("Timedout waiting for domain '%s', "
                                       "killing it!" % vm)
                    vm.kill()
            else:
                args.app.log.info('Shutting down {}'.format(vm))
                thread.start_new_thread(shutdown, (vm, ))
                waiting_for_shutdown[vm] = time.time()

        time.sleep(1)
        children = children_vms(args.domains)


if __name__ == '__main__':
    sys.exit(main())
