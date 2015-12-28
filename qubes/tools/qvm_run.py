#!/usr/bin/python2
# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010-2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015       Wojtek Porczyk <woju@invisiblethingslab.com>
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

from __future__ import print_function

import os
import sys

import qubes
import qubes.tools
import qubes.vm


parser = qubes.tools.QubesArgumentParser(
    want_vm=True,
    want_vm_all=True)

parser.add_argument('--user', '-u', metavar='USER',
    help='run command in a qube as USER')

parser.add_argument('--autostart', '--auto', '-a',
    action='store_true', default=False,
    help='start the qube if it is not running')

parser.add_argument('--pass-io', '-p',
    action='store_true', default=False,
    help='pass stdio from remote program')

parser.add_argument('--localcmd', metavar='COMMAND',
    help='with --pass-io, pass stdio to the given program')

parser.add_argument('--gui',
    action='store_true', default=True,
    help='run the command with GUI (default on)')

parser.add_argument('--no-gui', '--nogui',
    action='store_false', dest='gui',
    help='run the command without GUI')

parser.add_argument('--colour-output', '--color-output', metavar='COLOUR',
    action='store', dest='color_output', default=None,
    help='mark the qube output with given ANSI colour (ie. "31" for red)')

parser.add_argument('--no-colour-output', '--no-color-output',
    action='store_false', dest='color_output',
    help='disable colouring the stdio')

parser.add_argument('--filter-escape-chars',
    action='store_true', dest='filter_esc',
    default=os.isatty(sys.stdout.fileno()),
    help='filter terminal escape sequences (default if output is terminal)')

parser.add_argument('--no-filter-escape-chars',
    action='store_false', dest='filter_esc',
    help='do not filter terminal escape sequences; DANGEROUS when output is a'
        ' terminal emulator')

parser.add_argument('cmd', metavar='COMMAND',
    help='command to run')

#
#   parser.add_option ("-q", "--quiet", action="store_false", dest="verbose", default=True)
#   parser.add_option ("--tray", action="store_true", dest="tray", default=False,
#                      help="Use tray notifications instead of stdout" )
#   parser.add_option ("--pause", action="store_true", dest="pause", default=False,
#                     help="Do 'xl pause' for the VM(s) (can be combined this with --all)")
#   parser.add_option ("--unpause", action="store_true", dest="unpause", default=False,
#                     help="Do 'xl unpause' for the VM(s) (can be combined this with --all)")
#   parser.add_option ("--nogui", action="store_false", dest="gui", default=True,
#                     help="Run command without gui")
##

def main(args=None):
    args = parser.parse_args(args)
    if args.color_output is None and args.filter_esc:
        args.color_output = '31'

    if args.vm is qubes.tools.VM_ALL and args.passio:
        parser.error('--all and --passio are mutually exclusive')
    if args.color_output and not args.filter_esc:
        parser.error('--color-output must be used with --filter-escape-chars')

    retcode = 0
    for vm in app.vm:
        if args.color_output:
            sys.stdout.write('\033[0;{}m'.format(args.color_output))
            sys.stdout.flush()
        try:
            retcode = max(retcode, vm.run(args.cmd,
                user=args.user,
                autostart=args.autostart,
                passio=args.passio,
                localcmd=args.localcmd,
                gui=args.gui,
                filter_esc=args.filter_esc))
        except QubesException as e:
            if args.color_output:
                sys.stdout.write('\033[0m')
                sys.stdout.flush()
            vm.logger.error(str(e))
            return -1
        finally:
            if args.color_output:
                sys.stdout.write('\033[0;{}m'.format(args.color_output))
                sys.stdout.flush()

    return retcode


if __name__ == '__main__':
    sys.exit(main())
