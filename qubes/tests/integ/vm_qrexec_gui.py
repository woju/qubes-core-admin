#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2014-2015
#                   Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
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

from distutils import spawn

import multiprocessing
import os
import shlex
import subprocess
import unittest
import time

import qubes.config
import qubes.tests
import qubes.vm.appvm
import qubes.vm.templatevm
import re

TEST_DATA = b"0123456789" * 1024


class TC_00_AppVMMixin(qubes.tests.SystemTestsMixin):
    def setUp(self):
        super(TC_00_AppVMMixin, self).setUp()
        self.init_default_template(self.template)
        if self._testMethodName == 'test_210_time_sync':
            self.init_networking()
        self.testvm1 = self.app.add_new_vm(
            qubes.vm.appvm.AppVM,
            label='red',
            name=self.make_vm_name('vm1'),
            template=self.app.domains[self.template])
        self.testvm1.create_on_disk()
        self.testvm2 = self.app.add_new_vm(
            qubes.vm.appvm.AppVM,
            label='red',
            name=self.make_vm_name('vm2'),
            template=self.app.domains[self.template])
        self.testvm2.create_on_disk()
        self.app.save()

    def create_local_file(self, filename, content, mode='w'):
        with open(filename, mode) as file:
            file.write(content)
        self.addCleanup(os.unlink, filename)

    def create_remote_file(self, vm, filename, content):
        self.loop.run_until_complete(vm.run_for_stdio(
            'cat > {}'.format(shlex.quote(filename)),
            user='root', input=content.encode('utf-8')))

    def test_000_start_shutdown(self):
        self.testvm1.start()
        self.assertEquals(self.testvm1.get_power_state(), "Running")
        self.testvm1.shutdown()

        shutdown_counter = 0
        while self.testvm1.is_running():
            if shutdown_counter > qubes.config.defaults["shutdown_counter_max"]:
                self.fail("VM hanged during shutdown")
            shutdown_counter += 1
            time.sleep(1)
        time.sleep(1)
        self.assertEquals(self.testvm1.get_power_state(), "Halted")

    @unittest.skipUnless(spawn.find_executable('xdotool'),
                         "xdotool not installed")
    def test_010_run_xterm(self):
        self.testvm1.start()
        self.assertEquals(self.testvm1.get_power_state(), "Running")
        self.loop.run_until_complete(self.testvm1.run('xterm'))
        wait_count = 0
        title = 'user@{}'.format(self.testvm1.name)
        if self.template.count("whonix"):
            title = 'user@host'
        while subprocess.call(
                ['xdotool', 'search', '--name', title],
                stdout=open(os.path.devnull, 'w'),
                stderr=subprocess.STDOUT) > 0:
            wait_count += 1
            if wait_count > 100:
                self.fail("Timeout while waiting for xterm window")
            time.sleep(0.1)

        time.sleep(0.5)
        subprocess.check_call(
            ['xdotool', 'search', '--name', title,
             'windowactivate', 'type', 'exit\n'])

        wait_count = 0
        while subprocess.call(['xdotool', 'search', '--name', title],
                              stdout=open(os.path.devnull, 'w'),
                              stderr=subprocess.STDOUT) == 0:
            wait_count += 1
            if wait_count > 100:
                self.fail("Timeout while waiting for xterm "
                          "termination")
            time.sleep(0.1)

    @unittest.skipUnless(spawn.find_executable('xdotool'),
                         "xdotool not installed")
    def test_011_run_gnome_terminal(self):
        if "minimal" in self.template:
            self.skipTest("Minimal template doesn't have 'gnome-terminal'")
        self.testvm1.start()
        self.assertEquals(self.testvm1.get_power_state(), "Running")
        self.loop.run_until_complete(self.testvm1.run('gnome-terminal'))
        title = 'user@{}'.format(self.testvm1.name)
        if self.template.count("whonix"):
            title = 'user@host'
        wait_count = 0
        while subprocess.call(
                ['xdotool', 'search', '--name', title],
                stdout=open(os.path.devnull, 'w'),
                stderr=subprocess.STDOUT) > 0:
            wait_count += 1
            if wait_count > 100:
                self.fail("Timeout while waiting for gnome-terminal window")
            time.sleep(0.1)

        time.sleep(0.5)
        subprocess.check_call(
            ['xdotool', 'search', '--name', title,
             'windowactivate', '--sync', 'type', 'exit\n'])

        wait_count = 0
        while subprocess.call(['xdotool', 'search', '--name', title],
                              stdout=open(os.path.devnull, 'w'),
                              stderr=subprocess.STDOUT) == 0:
            wait_count += 1
            if wait_count > 100:
                self.fail("Timeout while waiting for gnome-terminal "
                          "termination")
            time.sleep(0.1)

    @unittest.skipUnless(spawn.find_executable('xdotool'),
                         "xdotool not installed")
    @unittest.expectedFailure
    def test_012_qubes_desktop_run(self):
        self.testvm1.start()
        self.assertEquals(self.testvm1.get_power_state(), "Running")
        xterm_desktop_path = "/usr/share/applications/xterm.desktop"
        # Debian has it different...
        xterm_desktop_path_debian = \
            "/usr/share/applications/debian-xterm.desktop"
        try:
            self.loop.run_until_complete(self.testvm1.run_for_stdio(
                'test -r {}'.format(xterm_desktop_path_debian)))
        except subprocess.CalledProcessError:
            pass
        else:
            xterm_desktop_path = xterm_desktop_path_debian
        self.loop.run_until_complete(
            self.testvm1.run('qubes-desktop-run {}'.format(xterm_desktop_path)))
        title = 'user@{}'.format(self.testvm1.name)
        if self.template.count("whonix"):
            title = 'user@host'
        wait_count = 0
        while subprocess.call(
                ['xdotool', 'search', '--name', title],
                stdout=open(os.path.devnull, 'w'),
                stderr=subprocess.STDOUT) > 0:
            wait_count += 1
            if wait_count > 100:
                self.fail("Timeout while waiting for xterm window")
            time.sleep(0.1)

        time.sleep(0.5)
        subprocess.check_call(
            ['xdotool', 'search', '--name', title,
             'windowactivate', '--sync', 'type', 'exit\n'])

        wait_count = 0
        while subprocess.call(['xdotool', 'search', '--name', title],
                              stdout=open(os.path.devnull, 'w'),
                              stderr=subprocess.STDOUT) == 0:
            wait_count += 1
            if wait_count > 100:
                self.fail("Timeout while waiting for xterm "
                          "termination")
            time.sleep(0.1)

    def test_050_qrexec_simple_eof(self):
        """Test for data and EOF transmission dom0->VM"""

        # XXX is this still correct? this is no longer simple qrexec,
        # but qubes.VMShell

        self.loop.run_until_complete(self.testvm1.start())
        try:
            (stdout, stderr) = self.loop.run_until_complete(asyncio.wait_for(
                self.testvm1.run_for_stdio('cat', input=TEST_DATA),
                timeout=10))
        except asyncio.TimeoutError:
            self.fail(
                "Timeout, probably EOF wasn't transferred to the VM process")

        self.assertEquals(stdout, TEST_DATA,
            'Received data differs from what was sent')
        self.assertFalse(stderr,
            'Some data was printed to stderr')

    def test_051_qrexec_simple_eof_reverse(self):
        """Test for EOF transmission VM->dom0"""

        @asyncio.coroutine
        def run(self):
            p = yield from self.testvm1.run(
                    'echo test; exec >&-; cat > /dev/null')

            # this will hang on test failure
            stdout = yield from p.stdout.read()

            p.stdin.write(TEST_DATA)
            yield from p.stdin.drain()
            p.stdin.close()
            self.assertEquals(stdout.strip(), 'test',
                'Received data differs from what was expected')
            # this may hang in some buggy cases
            self.assertFalse((yield from p.stderr.read()),
                'Some data was printed to stderr')

            try:
                yield from asyncio.wait_for(p.wait(), timeout=1)
            except asyncio.TimeoutError:
                self.fail("Timeout, "
                    "probably EOF wasn't transferred from the VM process")

        self.loop.run_until_complete(self.testvm1.start())
        self.loop.run_until_complete(run(self))

    def test_052_qrexec_vm_service_eof(self):
        """Test for EOF transmission VM(src)->VM(dst)"""

        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))
        self.loop.run_until_complete(self.testvm2.run_for_stdio(
            'cat > /etc/qubes-rpc/test.EOF',
            user='root',
            input=b'/bin/cat'))

        self.create_local_file('/etc/qubes-rpc/policy/test.EOF',
            '{} {} allow'.format(self.testvm1.name, self.testvm2.name))

        try:
            (stdout, _) = self.loop.run_until_complete(asyncio.wait_for(
                self.testvm1.run_for_stdio('''\
                    /usr/lib/qubes/qrexec-client-vm {} test.EOF \
                        /bin/sh -c 'echo test; exec >&-; cat >&$SAVED_FD_1'
                '''.format(self.testvm2.name)),
                timeout=10))

        except asyncio.TimeoutError:
            self.fail("Timeout, probably EOF wasn't transferred")

        self.assertEquals(stdout, b'test',
            'Received data differs from what was expected')

    @unittest.expectedFailure
    def test_053_qrexec_vm_service_eof_reverse(self):
        """Test for EOF transmission VM(src)<-VM(dst)"""

        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))
        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.EOF',
                'echo test; exec >&-; cat >/dev/null')
        self.create_local_file('/etc/qubes-rpc/policy/test.EOF',
            '{} {} allow'.format(self.testvm1.name, self.testvm2.name))

        try:
            (stdout, _) = self.loop.run_until_complete(asyncio.wait_for(
                self.testvm1.run_for_stdio('''\
                    /usr/lib/qubes/qrexec-client-vm %s test.EOF \
                        /bin/sh -c 'cat >&$SAVED_FD_1'
                    '''.format(self.testvm2.name))
                timeout=10))

        except asyncio.TimeoutError:
            self.fail("Timeout, probably EOF wasn't transferred")

        self.assertEquals(stdout, b'test',
            'Received data differs from what was expected')

    def test_055_qrexec_dom0_service_abort(self):
        """
        Test if service abort (by dom0) is properly handled by source VM.

        If "remote" part of the service terminates, the source part should
        properly be notified. This includes closing its stdin (which is
        already checked by test_053_qrexec_vm_service_eof_reverse), but also
        its stdout - otherwise such service might hang on write(2) call.
        """

        self.loop.run_until_complete(self.testvm1.start())
        self.create_local_file('/etc/qubes-rpc/test.Abort',
            'sleep 1')
        self.create_local_file('/etc/qubes-rpc/policy/test.Abort',
            '{} dom0 allow'.format(self.testvm1.name))

        try:
            (stdout, _) = self.loop.run_until_complete(asyncio.wait_for(
                self.testvm1.run_for_stdio('''\
                    /usr/lib/qubes/qrexec-client-vm dom0 test.Abort \
                        /bin/cat /dev/zero'''),
                timeout=10))
        except asyncio.TimeoutError:
            self.fail("Timeout, probably stdout wasn't closed")

    def test_060_qrexec_exit_code_dom0(self):
        self.loop.run_until_complete(self.testvm1.start())
        self.loop.run_until_complete(self.testvm1.run_for_stdio('exit 0'))
        with self.assertRaises(subprocess.CalledProcessError):
            self.loop.run_until_complete(self.testvm1.run_for_stdio('exit 3'))

    @unittest.expectedFailure
    def test_065_qrexec_exit_code_vm(self):
        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))

        self.create_local_file('/etc/qubes-rpc/policy/test.Retcode',
            '{} {} allow'.format(self.testvm1.name, self.testvm2.name))

        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.Retcode',
            'exit 0')
        (stdout, stderr) = self.loop.run_until_complete(
            self.testvm1.run_for_stdio('''\
                /usr/lib/qubes/qrexec-client-vm {} test.Retcode \
                    /bin/sh -c 'cat >/dev/null';
                    echo $?'''.format(self.testvm1.name)))
        self.assertEqual(stdout, b'0\n')

        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.Retcode',
            'exit 3')
        (stdout, stderr) = self.loop.run_until_complete(
            self.testvm1.run_for_stdio('''\
                /usr/lib/qubes/qrexec-client-vm {} test.Retcode \
                    /bin/sh -c 'cat >/dev/null';
                    echo $?'''.format(self.testvm1.name)))
        self.assertEqual(stdout, b'3\n')

    def test_070_qrexec_vm_simultaneous_write(self):
        """Test for simultaneous write in VM(src)->VM(dst) connection

            This is regression test for #1347

            Check for deadlock when initially both sides writes a lot of data
            (and not read anything). When one side starts reading, it should
            get the data and the remote side should be possible to write then more.
            There was a bug where remote side was waiting on write(2) and not
            handling anything else.
        """

        def run(self):
            # first write a lot of data to fill all the buffers
            # then after some time start reading
            p.communicate()
            result.value = p.returncode

        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))

        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.write', '''\
            # first write a lot of data
            dd if=/dev/zero bs=993 count=10000 iflag=fullblock
            # and only then read something
            dd of=/dev/null bs=993 count=10000 iflag=fullblock
            ''')
        self.create_local_file('/etc/qubes-rpc/policy/test.write',
            '{} {} allow'.format(self.testvm1.name, self.testvm2.name))

        try:
            self.loop.run_until_complete(asyncio.wait_for(
                self.testvm1.run_for_stdio('''\
                    /usr/lib/qubes/qrexec-client-vm {} test.write /bin/sh -c '
                        dd if=/dev/zero bs=993 count=10000 iflag=fullblock &
                        sleep 1;
                        dd of=/dev/null bs=993 count=10000 iflag=fullblock;
                        wait'
                    '''.format(self.testvm2.name)), timeout=10))
        except subprocess.CalledProcessError:
            self.fail('Service call failed')
        except asyncio.TimeoutError:
            self.fail('Timeout, probably deadlock')

    @unittest.skip('localcmd= argument went away')
    def test_071_qrexec_dom0_simultaneous_write(self):
        """Test for simultaneous write in dom0(src)->VM(dst) connection

            Similar to test_070_qrexec_vm_simultaneous_write, but with dom0
            as a source.
        """
        def run(self):
            result.value = self.testvm2.run_service(
                "test.write", localcmd="/bin/sh -c '"
                # first write a lot of data to fill all the buffers
                "dd if=/dev/zero bs=993 count=10000 iflag=fullblock & "
                # then after some time start reading
                "sleep 1; "
                "dd of=/dev/null bs=993 count=10000 iflag=fullblock; "
                "wait"
                "'")

        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.write', '''\
            # first write a lot of data
            dd if=/dev/zero bs=993 count=10000 iflag=fullblock
            # and only then read something
            dd of=/dev/null bs=993 count=10000 iflag=fullblock
            ''')
        self.create_local_file('/etc/qubes-rpc/policy/test.write',
            '{} {} allow'.format(self.testvm1.name, self.testvm2.name))

        t = multiprocessing.Process(target=run, args=(self,))
        t.start()
        t.join(timeout=10)
        if t.is_alive():
            t.terminate()
            self.fail("Timeout, probably deadlock")
        self.assertEqual(result.value, 0, "Service call failed")

    @unittest.skip('localcmd= argument went away')
    def test_072_qrexec_to_dom0_simultaneous_write(self):
        """Test for simultaneous write in dom0(src)<-VM(dst) connection

            Similar to test_071_qrexec_dom0_simultaneous_write, but with dom0
            as a "hanging" side.
        """
        result = multiprocessing.Value('i', -1)

        def run(self):
            result.value = self.testvm2.run_service(
                "test.write", localcmd="/bin/sh -c '"
                # first write a lot of data to fill all the buffers
                "dd if=/dev/zero bs=993 count=10000 iflag=fullblock "
                # then, only when all written, read something
                "dd of=/dev/null bs=993 count=10000 iflag=fullblock; "
                "'")

        self.testvm2.start()
        p = self.testvm2.run("cat > /etc/qubes-rpc/test.write", user="root",
                             passio_popen=True)
        # first write a lot of data
        p.stdin.write(b"dd if=/dev/zero bs=993 count=10000 iflag=fullblock &\n")
        # and only then read something
        p.stdin.write(b"dd of=/dev/null bs=993 count=10000 iflag=fullblock\n")
        p.stdin.write(b"sleep 1; \n")
        p.stdin.write(b"wait\n")
        p.stdin.close()
        p.wait()
        policy = open("/etc/qubes-rpc/policy/test.write", "w")
        policy.write("%s %s allow" % (self.testvm1.name, self.testvm2.name))
        policy.close()
        self.addCleanup(os.unlink, "/etc/qubes-rpc/policy/test.write")

        t = multiprocessing.Process(target=run, args=(self,))
        t.start()
        t.join(timeout=10)
        if t.is_alive():
            t.terminate()
            self.fail("Timeout, probably deadlock")
        self.assertEqual(result.value, 0, "Service call failed")

    def test_080_qrexec_service_argument_allow_default(self):
        """Qrexec service call with argument"""

        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))

        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.Argument',
            '/usr/bin/printf %s "$1"')
        self.create_local_file('/etc/qubes-rpc/policy/test.Argument',
            '{} {} allow'.format(self.testvm1.name, self.testvm2.name))

        (stdout, stderr) = self.loop.run_until_complete(self.testvm1.run(
            '/usr/lib/qubes/qrexec-client-vm {} test.Argument+argument'.format(
                self.testvm2.name))
        self.assertEqual(stdout, b"argument\n")

    def test_081_qrexec_service_argument_allow_specific(self):
        """Qrexec service call with argument - allow only specific value"""

        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))

        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.Argument',
            '/usr/bin/printf %s "$1"')

        self.create_local_file('/etc/qubes-rpc/policy/test.Argument',
            '$anyvm $anyvm deny')
        self.create_local_file('/etc/qubes-rpc/policy/test.Argument+argument',
            '{} {} allow'.format(self.testvm1.name, self.testvm2.name))

        (stdout, stderr) = self.loop.run_until_complete(self.testvm1.run(
            '/usr/lib/qubes/qrexec-client-vm {} test.Argument+argument'.format(
                self.testvm2.name))
        self.assertEqual(stdout, b"argument\n")

    def test_082_qrexec_service_argument_deny_specific(self):
        """Qrexec service call with argument - deny specific value"""
        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))

        self.create_remote_file(testvm2, '/etc/qubes-rpc/test.Argument',
            '/usr/bin/printf %s "$1"')
        self.create_local_file('/etc/qubes-rpc/policy/test.Argument',
            '$anyvm $anyvm allow')
        self.create_local_file('/etc/qubes-rpc/policy/test.Argument+argument',
            '{} {} deny'.format(self.testvm1.name, self.testvm2.name))

        with self.assertRaises(subprocess.CalledProcessError,
                'Service request should be denied'):
            self.loop.run_until_complete(
                self.testvm1.run('/usr/lib/qubes/qrexec-client-vm {} '
                    'test.Argument+argument'.format(self.testvm2.name))

    def test_083_qrexec_service_argument_specific_implementation(self):
        """Qrexec service call with argument - argument specific
        implementatation"""
        self.testvm1.start()
        self.testvm2.start()
        p = self.testvm2.run("cat > /etc/qubes-rpc/test.Argument", user="root",
                             passio_popen=True)
        p.communicate(b"/bin/echo $1")

        p = self.testvm2.run("cat > /etc/qubes-rpc/test.Argument+argument",
            user="root", passio_popen=True)
        p.communicate(b"/bin/echo specific: $1")

        with open("/etc/qubes-rpc/policy/test.Argument", "w") as policy:
            policy.write("%s %s allow" % (self.testvm1.name, self.testvm2.name))
        self.addCleanup(os.unlink, "/etc/qubes-rpc/policy/test.Argument")

        p = self.testvm1.run("/usr/lib/qubes/qrexec-client-vm {} "
                             "test.Argument+argument".format(self.testvm2.name),
                             passio_popen=True)
        (stdout, stderr) = p.communicate()
        self.assertEqual(stdout, b"specific: argument\n")

    def test_084_qrexec_service_argument_extra_env(self):
        """Qrexec service call with argument - extra env variables"""
        self.testvm1.start()
        self.testvm2.start()
        p = self.testvm2.run("cat > /etc/qubes-rpc/test.Argument", user="root",
                             passio_popen=True)
        p.communicate(b"/bin/echo $QREXEC_SERVICE_FULL_NAME "
                      b"$QREXEC_SERVICE_ARGUMENT")

        with open("/etc/qubes-rpc/policy/test.Argument", "w") as policy:
            policy.write("%s %s allow" % (self.testvm1.name, self.testvm2.name))
        self.addCleanup(os.unlink, "/etc/qubes-rpc/policy/test.Argument")

        p = self.testvm1.run("/usr/lib/qubes/qrexec-client-vm {} "
                             "test.Argument+argument".format(self.testvm2.name),
                             passio_popen=True)
        (stdout, stderr) = p.communicate()
        self.assertEqual(stdout, b"test.Argument+argument argument\n")

    def test_100_qrexec_filecopy(self):
        self.testvm1.start()
        self.testvm2.start()
        self.qrexec_policy('qubes.Filecopy', self.testvm1.name,
            self.testvm2.name)
        p = self.testvm1.run("qvm-copy-to-vm %s /etc/passwd" %
                             self.testvm2.name, passio_popen=True,
                             passio_stderr=True)
        p.wait()
        self.assertEqual(p.returncode, 0, "qvm-copy-to-vm failed: %s" %
                         p.stderr.read())
        retcode = self.testvm2.run("diff /etc/passwd "
                                   "/home/user/QubesIncoming/{}/passwd".format(
                                       self.testvm1.name),
                                   wait=True)
        self.assertEqual(retcode, 0, "file differs")

    def test_105_qrexec_filemove(self):
        self.testvm1.start()
        self.testvm2.start()
        self.qrexec_policy('qubes.Filecopy', self.testvm1.name,
            self.testvm2.name)
        retcode = self.testvm1.run("cp /etc/passwd passwd", wait=True)
        assert retcode == 0, "Failed to prepare source file"
        p = self.testvm1.run("qvm-move-to-vm %s passwd" %
                             self.testvm2.name, passio_popen=True,
                             passio_stderr=True)
        p.wait()
        self.assertEqual(p.returncode, 0, "qvm-move-to-vm failed: %s" %
                         p.stderr.read())
        retcode = self.testvm2.run("diff /etc/passwd "
                                   "/home/user/QubesIncoming/{}/passwd".format(
                                       self.testvm1.name),
                                   wait=True)
        self.assertEqual(retcode, 0, "file differs")
        retcode = self.testvm1.run("test -f passwd", wait=True)
        self.assertEqual(retcode, 1, "source file not removed")

    def test_101_qrexec_filecopy_with_autostart(self):
        self.testvm1.start()
        self.qrexec_policy('qubes.Filecopy', self.testvm1.name,
            self.testvm2.name)
        p = self.testvm1.run("qvm-copy-to-vm %s /etc/passwd" %
                             self.testvm2.name, passio_popen=True,
                             passio_stderr=True)
        p.wait()
        self.assertEqual(p.returncode, 0, "qvm-copy-to-vm failed: %s" %
                         p.stderr.read())
        # workaround for libvirt bug (domain ID isn't updated when is started
        #  from other application) - details in
        # QubesOS/qubes-core-libvirt@63ede4dfb4485c4161dd6a2cc809e8fb45ca664f
        self.testvm2._libvirt_domain = None
        self.assertTrue(self.testvm2.is_running())
        retcode = self.testvm2.run("diff /etc/passwd "
                                   "/home/user/QubesIncoming/{}/passwd".format(
                                       self.testvm1.name),
                                   wait=True)
        self.assertEqual(retcode, 0, "file differs")

    def test_110_qrexec_filecopy_deny(self):
        self.testvm1.start()
        self.testvm2.start()
        self.qrexec_policy('qubes.Filecopy', self.testvm1.name,
            self.testvm2.name, allow=False)
        p = self.testvm1.run("qvm-copy-to-vm %s /etc/passwd" %
                             self.testvm2.name, passio_popen=True)
        p.wait()
        self.assertNotEqual(p.returncode, 0, "qvm-copy-to-vm unexpectedly "
                            "succeeded")
        retcode = self.testvm1.run("ls /home/user/QubesIncoming/%s" %
                                   self.testvm1.name, wait=True,
                                   ignore_stderr=True)
        self.assertNotEqual(retcode, 0, "QubesIncoming exists although file "
                            "copy was denied")

    @unittest.skip("Xen gntalloc driver crashes when page is mapped in the "
                   "same domain")
    def test_120_qrexec_filecopy_self(self):
        self.testvm1.start()
        self.qrexec_policy('qubes.Filecopy', self.testvm1.name,
            self.testvm1.name)
        p = self.testvm1.run("qvm-copy-to-vm %s /etc/passwd" %
                             self.testvm1.name, passio_popen=True,
                             passio_stderr=True)
        p.wait()
        self.assertEqual(p.returncode, 0, "qvm-copy-to-vm failed: %s" %
                         p.stderr.read())
        retcode = self.testvm1.run(
            "diff /etc/passwd /home/user/QubesIncoming/{}/passwd".format(
                self.testvm1.name),
            wait=True)
        self.assertEqual(retcode, 0, "file differs")

    @unittest.skipUnless(spawn.find_executable('xdotool'),
                         "xdotool not installed")
    def test_130_qrexec_filemove_disk_full(self):
        self.testvm1.start()
        self.testvm2.start()
        self.qrexec_policy('qubes.Filecopy', self.testvm1.name,
            self.testvm2.name)
        # Prepare test file
        prepare_cmd = ("yes teststring | dd of=testfile bs=1M "
                       "count=50 iflag=fullblock")
        retcode = self.testvm1.run(prepare_cmd, wait=True)
        if retcode != 0:
            raise RuntimeError("Failed '{}' in {}".format(prepare_cmd,
                                                          self.testvm1.name))
        # Prepare target directory with limited size
        prepare_cmd = (
            "mkdir -p /home/user/QubesIncoming && "
            "chown user /home/user/QubesIncoming && "
            "mount -t tmpfs none /home/user/QubesIncoming -o size=48M"
        )
        retcode = self.testvm2.run(prepare_cmd, user="root", wait=True)
        if retcode != 0:
            raise RuntimeError("Failed '{}' in {}".format(prepare_cmd,
                                                          self.testvm2.name))
        p = self.testvm1.run("qvm-move-to-vm %s testfile" %
                             self.testvm2.name, passio_popen=True,
                             passio_stderr=True)
        # Close GUI error message
        self.enter_keys_in_window('Error', ['Return'])
        p.wait()
        self.assertNotEqual(p.returncode, 0, "qvm-move-to-vm should fail")
        retcode = self.testvm1.run("test -f testfile", wait=True)
        self.assertEqual(retcode, 0, "testfile should not be deleted in "
                                     "source VM")

    def test_200_timezone(self):
        """Test whether timezone setting is properly propagated to the VM"""
        if "whonix" in self.template:
            self.skipTest("Timezone propagation disabled on Whonix templates")

        self.testvm1.start()
        (vm_tz, _) = self.testvm1.run("date +%Z",
                                      passio_popen=True).communicate()
        (dom0_tz, _) = subprocess.Popen(["date", "+%Z"],
                                        stdout=subprocess.PIPE).communicate()
        self.assertEqual(vm_tz.strip(), dom0_tz.strip())

        # Check if reverting back to UTC works
        (vm_tz, _) = self.testvm1.run("TZ=UTC date +%Z",
                                      passio_popen=True).communicate()
        self.assertEqual(vm_tz.strip(), b"UTC")

    def test_210_time_sync(self):
        """Test time synchronization mechanism"""
        if self.template.startswith('whonix-'):
            self.skipTest('qvm-sync-clock disabled for Whonix VMs')
        self.testvm1.start()
        self.testvm2.start()
        (start_time, _) = subprocess.Popen(["date", "-u", "+%s"],
                                           stdout=subprocess.PIPE).communicate()
        try:
            self.app.clockvm = self.testvm1
            self.app.save()
            # break vm and dom0 time, to check if qvm-sync-clock would fix it
            subprocess.check_call(["sudo", "date", "-s",
                                   "2001-01-01T12:34:56"],
                                  stdout=open(os.devnull, 'w'))
            retcode = self.testvm1.run("date -s 2001-01-01T12:34:56",
                                       user="root", wait=True)
            self.assertEquals(retcode, 0, "Failed to break the VM(1) time")
            retcode = self.testvm2.run("date -s 2001-01-01T12:34:56",
                                       user="root", wait=True)
            self.assertEquals(retcode, 0, "Failed to break the VM(2) time")
            retcode = subprocess.call(["qvm-sync-clock"])
            self.assertEquals(retcode, 0,
                              "qvm-sync-clock failed with code {}".
                              format(retcode))
            # qvm-sync-clock is asynchronous - it spawns qubes.SetDateTime
            # service, send it timestamp value and exists without waiting for
            # actual time set
            time.sleep(1)
            (vm_time, _) = self.testvm1.run("date -u +%s",
                                            passio_popen=True).communicate()
            self.assertAlmostEquals(int(vm_time), int(start_time), delta=30)
            (vm_time, _) = self.testvm2.run("date -u +%s",
                                            passio_popen=True).communicate()
            self.assertAlmostEquals(int(vm_time), int(start_time), delta=30)
            (dom0_time, _) = subprocess.Popen(["date", "-u", "+%s"],
                                              stdout=subprocess.PIPE
                                              ).communicate()
            self.assertAlmostEquals(int(dom0_time), int(start_time), delta=30)

        except:
            # reset time to some approximation of the real time
            subprocess.Popen(
                ["sudo", "date", "-u", "-s", "@" + start_time.decode()])
            raise

    @unittest.expectedFailure
    def test_250_resize_private_img(self):
        """
        Test private.img resize, both offline and online
        :return:
        """
        # First offline test
        self.testvm1.storage.resize('private', 4*1024**3)
        self.testvm1.start()
        df_cmd = '( df --output=size /rw || df /rw | awk \'{print $2}\' )|' \
                 'tail -n 1'
        p = self.testvm1.run(df_cmd,
                             passio_popen=True)
        # new_size in 1k-blocks
        (new_size, _) = p.communicate()
        # some safety margin for FS metadata
        self.assertGreater(int(new_size.strip()), 3.8*1024**2)
        # Then online test
        self.testvm1.storage.resize('private', 6*1024**3)
        p = self.testvm1.run(df_cmd,
                             passio_popen=True)
        # new_size in 1k-blocks
        (new_size, _) = p.communicate()
        # some safety margin for FS metadata
        self.assertGreater(int(new_size.strip()), 5.8*1024**2)

    @unittest.skipUnless(spawn.find_executable('xdotool'),
                         "xdotool not installed")
    def test_300_bug_1028_gui_memory_pinning(self):
        """
        If VM window composition buffers are relocated in memory, GUI will
        still use old pointers and will display old pages
        :return:
        """
        self.testvm1.memory = 800
        self.testvm1.maxmem = 800
        # exclude from memory balancing
        self.testvm1.features['services/meminfo-writer'] = False
        self.testvm1.start()
        # and allow large map count
        self.testvm1.run("echo 256000 > /proc/sys/vm/max_map_count",
            user="root", wait=True)
        allocator_c = (
            "#include <sys/mman.h>\n"
            "#include <stdlib.h>\n"
            "#include <stdio.h>\n"
            "\n"
            "int main(int argc, char **argv) {\n"
            "	int total_pages;\n"
            "	char *addr, *iter;\n"
            "\n"
            "	total_pages = atoi(argv[1]);\n"
            "	addr = mmap(NULL, total_pages * 0x1000, PROT_READ | "
            "PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE | MAP_POPULATE, -1, 0);\n"
            "	if (addr == MAP_FAILED) {\n"
            "		perror(\"mmap\");\n"
            "		exit(1);\n"
            "	}\n"
            "	printf(\"Stage1\\n\");\n"
            "   fflush(stdout);\n"
            "	getchar();\n"
            "	for (iter = addr; iter < addr + total_pages*0x1000; iter += "
            "0x2000) {\n"
            "		if (mlock(iter, 0x1000) == -1) {\n"
            "			perror(\"mlock\");\n"
            "           fprintf(stderr, \"%d of %d\\n\", (iter-addr)/0x1000, "
            "total_pages);\n"
            "			exit(1);\n"
            "		}\n"
            "	}\n"
            "	printf(\"Stage2\\n\");\n"
            "   fflush(stdout);\n"
            "	for (iter = addr+0x1000; iter < addr + total_pages*0x1000; "
            "iter += 0x2000) {\n"
            "		if (munmap(iter, 0x1000) == -1) {\n"
            "			perror(\"munmap\");\n"
            "			exit(1);\n"
            "		}\n"
            "	}\n"
            "	printf(\"Stage3\\n\");\n"
            "   fflush(stdout);\n"
            "   fclose(stdout);\n"
            "	getchar();\n"
            "\n"
            "	return 0;\n"
            "}\n")

        p = self.testvm1.run("cat > allocator.c", passio_popen=True)
        p.communicate(allocator_c.encode())
        p = self.testvm1.run("gcc allocator.c -o allocator",
            passio_popen=True, passio_stderr=True)
        (stdout, stderr) = p.communicate()
        if p.returncode != 0:
            self.skipTest("allocator compile failed: {}".format(stderr))

        # drop caches to have even more memory pressure
        self.testvm1.run("echo 3 > /proc/sys/vm/drop_caches",
            user="root", wait=True)

        # now fragment all free memory
        p = self.testvm1.run("grep ^MemFree: /proc/meminfo|awk '{print $2}'",
            passio_popen=True)
        memory_pages = int(p.communicate()[0].strip())
        memory_pages //= 4 # 4k pages
        alloc1 = self.testvm1.run(
            "ulimit -l unlimited; exec /home/user/allocator {}".format(
                memory_pages),
            user="root", passio_popen=True, passio_stderr=True)
        # wait for memory being allocated; can't use just .read(), because EOF
        # passing is unreliable while the process is still running
        alloc1.stdin.write(b"\n")
        alloc1.stdin.flush()
        alloc_out = alloc1.stdout.read(len("Stage1\nStage2\nStage3\n"))

        if b"Stage3" not in alloc_out:
            # read stderr only in case of failed assert, but still have nice
            # failure message (don't use self.fail() directly)
            self.assertIn(b"Stage3", alloc_out, alloc1.stderr.read())

        # now, launch some window - it should get fragmented composition buffer
        # it is important to have some changing content there, to generate
        # content update events (aka damage notify)
        proc = self.testvm1.run("gnome-terminal --full-screen -e top",
            passio_popen=True)

        # help xdotool a little...
        time.sleep(2)
        # get window ID
        search = subprocess.Popen(['xdotool', 'search', '--sync',
            '--onlyvisible', '--class', self.testvm1.name + ':.*erminal'],
            stdout=subprocess.PIPE)
        winid = search.communicate()[0].strip()
        xprop = subprocess.Popen(['xprop', '-notype', '-id', winid,
            '_QUBES_VMWINDOWID'], stdout=subprocess.PIPE)
        vm_winid = xprop.stdout.read().decode().strip().split(' ')[4]

        # now free the fragmented memory and trigger compaction
        alloc1.stdin.write(b"\n")
        alloc1.stdin.flush()
        alloc1.wait()
        self.testvm1.run("echo 1 > /proc/sys/vm/compact_memory", user="root")

        # now window may be already "broken"; to be sure, allocate (=zero)
        # some memory
        alloc2 = self.testvm1.run(
            "ulimit -l unlimited; /home/user/allocator {}".format(memory_pages),
            user="root", passio_popen=True, passio_stderr=True)
        alloc2.stdout.read(len("Stage1\n"))

        # wait for damage notify - top updates every 3 sec by default
        time.sleep(6)

        # now take screenshot of the window, from dom0 and VM
        # choose pnm format, as it doesn't have any useless metadata - easy
        # to compare
        p = self.testvm1.run("import -window {} pnm:-".format(vm_winid),
            passio_popen=True, passio_stderr=True)
        (vm_image, stderr) = p.communicate()
        if p.returncode != 0:
            raise Exception("Failed to get VM window image: {}".format(
                stderr))

        p = subprocess.Popen(["import", "-window", winid, "pnm:-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (dom0_image, stderr) = p.communicate()
        if p.returncode != 0:
            raise Exception("Failed to get dom0 window image: {}".format(
                stderr))

        if vm_image != dom0_image:
            self.fail("Dom0 window doesn't match VM window content")

class TC_10_Generic(qubes.tests.SystemTestsMixin, qubes.tests.QubesTestCase):
    def setUp(self):
        super(TC_10_Generic, self).setUp()
        self.init_default_template()
        self.vm = self.app.add_new_vm(
            qubes.vm.appvm.AppVM,
            name=self.make_vm_name('vm'),
            label='red',
            template=self.app.default_template)
        self.vm.create_on_disk()
        self.save_and_reload_db()
        self.vm = self.app.domains[self.vm.qid]

    def test_000_anyvm_deny_dom0(self):
        '''$anyvm in policy should not match dom0'''
        policy = open("/etc/qubes-rpc/policy/test.AnyvmDeny", "w")
        policy.write("%s $anyvm allow" % (self.vm.name,))
        policy.close()
        self.addCleanup(os.unlink, "/etc/qubes-rpc/policy/test.AnyvmDeny")

        flagfile = '/tmp/test-anyvmdeny-flag'
        if os.path.exists(flagfile):
            os.remove(flagfile)
        with open('/etc/qubes-rpc/test.AnyvmDeny', 'w') as f:
            f.write('touch {}\n'.format(flagfile))
            f.write('echo service output\n')
        self.addCleanup(os.unlink, "/etc/qubes-rpc/test.AnyvmDeny")

        self.vm.start()
        p = self.vm.run("/usr/lib/qubes/qrexec-client-vm dom0 test.AnyvmDeny",
                             passio_popen=True, passio_stderr=True)
        (stdout, stderr) = p.communicate()
        self.assertEqual(p.returncode, 1,
            '$anyvm matched dom0, qrexec-client-vm output: {}'.
                format(stdout + stderr))
        self.assertFalse(os.path.exists(flagfile),
            'Flag file created (service was run) even though should be denied,'
            ' qrexec-client-vm output: {}'.format(stdout + stderr))


def load_tests(loader, tests, pattern):
    try:
        app = qubes.Qubes()
        templates = [vm.name for vm in app.domains if
                     isinstance(vm, qubes.vm.templatevm.TemplateVM)]
    except OSError:
        templates = []
    for template in templates:
        tests.addTests(loader.loadTestsFromTestCase(
            type(
                'TC_00_AppVM_' + template,
                (TC_00_AppVMMixin, qubes.tests.QubesTestCase),
                {'template': template})))

    return tests
