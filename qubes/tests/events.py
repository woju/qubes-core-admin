#!/usr/bin/python2 -O
# vim: fileencoding=utf-8

#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2014-2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2014-2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

import qubes.events
import qubes.tests

class TC_00_Emitter(qubes.tests.QubesTestCase):
    def test_000_add_handler(self):
        # need something mutable
        testevent_fired = [False]

        def on_testevent(subject, event):
            # pylint: disable=unused-argument
            if event == 'testevent':
                testevent_fired[0] = True

        emitter = qubes.events.Emitter()
        emitter.add_handler('testevent', on_testevent)
        emitter.events_enabled = True
        emitter.fire_event('testevent')
        self.assertTrue(testevent_fired[0])


    def test_001_decorator(self):
        class TestEmitter(qubes.events.Emitter):
            def __init__(self):
                # pylint: disable=bad-super-call
                super(TestEmitter, self).__init__()
                self.testevent_fired = False

            @qubes.events.handler('testevent')
            def on_testevent(self, event):
                if event == 'testevent':
                    self.testevent_fired = True

        emitter = TestEmitter()
        emitter.events_enabled = True
        emitter.fire_event('testevent')
        self.assertTrue(emitter.testevent_fired)

    def test_002_fire_for_effect(self):
        class TestEmitter(qubes.events.Emitter):
            @qubes.events.handler('testevent')
            def on_testevent_1(self, event):
                pass

            @qubes.events.handler('testevent')
            def on_testevent_2(self, event):
                yield 'testvalue1'
                yield 'testvalue2'

            @qubes.events.handler('testevent')
            def on_testevent_3(self, event):
                return ('testvalue3', 'testvalue4')

        emitter = TestEmitter()
        emitter.events_enabled = True
        emitter.fire_event('testevent')

        effect = emitter.fire_event('testevent')

        self.assertCountEqual(effect,
            ('testvalue1', 'testvalue2', 'testvalue3', 'testvalue4'))

    def test_004_catch_all(self):
        # need something mutable
        testevent_fired = [0]

        def on_all(subject, event, *args, **kwargs):
            # pylint: disable=unused-argument
            testevent_fired[0] += 1

        def on_foo(subject, event, *args, **kwargs):
            # pylint: disable=unused-argument
            testevent_fired[0] += 1

        emitter = qubes.events.Emitter()
        emitter.add_handler('*', on_all)
        emitter.add_handler('foo', on_foo)
        emitter.events_enabled = True
        emitter.fire_event('testevent')
        self.assertEqual(testevent_fired[0], 1)
        emitter.fire_event('foo')
        # now catch-all and foo should be executed
        self.assertEqual(testevent_fired[0], 3)
        emitter.fire_event('bar')
        self.assertEqual(testevent_fired[0], 4)
