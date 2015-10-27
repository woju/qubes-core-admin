#!/usr/bin/python2 -O
# vim: fileencoding=utf-8

#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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


import qubes
import qubes.tools.qubes_create

import qubes.tests

@qubes.tests.skipUnlessDom0
class TC_00_qubes_create(qubes.tests.SystemTestsMixin, qubes.tests.QubesTestCase):
    def tearDown(self):
        self.remove_vms(vm for vm in qubes.Qubes(qubes.tests.XMLPATH).domain
            if vm.name != qubes.tests.TEMPLATE)
        os.unlink(qubes.tests.XMLPATH)

    def test_000_basic(self):
        self.assertEqual(0,
            qubes.tools.qubes_create.main((
                '--qubesxml', qubes.tests.XMLPATH,
                )))

    def test_001_property(self):
        self.assertEqual(0,
            qubes.tools.qubes_create.main((
                '--qubesxml', qubes.tests.XMLPATH,
                '--property', 'default_kernel=testkernel'
                )))

        self.assertEqual('testkernel',
            qubes.Qubes(qubes.tests.XMLPATH).default_kernel)
