# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
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
# with this program; if not, see <http://www.gnu.org/licenses/>.

''' Internal interface for dom0 components to communicate with qubesd. '''

import asyncio
import json

import qubes.mgmt


class QubesInternalMgmt(object):
    ''' Communication interface for dom0 components,
    by design the input here is trusted.'''
    def __init__(self, app, src, method, dest, arg):
        self.app = app

        self.src = self.app.domains[src.decode('ascii')]
        self.dest = self.app.domains[dest.decode('ascii')]
        self.arg = arg.decode('ascii')

        self.method = method.decode('ascii')

        func_name = self.method
        assert func_name.startswith('mgmtinternal.')
        func_name = func_name[len('mgmtinternal.'):]
        func_name = func_name.lower().replace('.', '_')

        if func_name.startswith('_'):
            raise qubes.mgmt.ProtocolError(
                'possibly malicious function name: {!r}'.format(
                    func_name))

        try:
            func = getattr(self, func_name)
        except AttributeError:
            raise qubes.mgmt.ProtocolError(
                'no such attribute: {!r}'.format(
                    func_name))

        if not asyncio.iscoroutinefunction(func):
            raise qubes.mgmt.ProtocolError(
                'no such method: {!r}'.format(
                    func_name))

        self.execute = func
        del func_name
        del func

    #
    # PRIVATE METHODS, not to be called via RPC
    #

    #
    # ACTUAL RPC CALLS
    #

    @asyncio.coroutine
    def getsysteminfo(self, untrusted_payload):
        assert self.dest.name == 'dom0'
        assert not self.arg
        assert not untrusted_payload
        del untrusted_payload

        system_info = {'domains': {
            domain.name: {
                'tags': list(domain.tags),
                'type': domain.__class__.__name__,
                'dispvm_allowed': getattr(domain, 'dispvm_allowed', False),
                'default_dispvm': (str(domain.default_dispvm) if
                    domain.default_dispvm else None),
                'icon': str(domain.label.icon),
            } for domain in self.app.domains
        }}

        return json.dumps(system_info)

