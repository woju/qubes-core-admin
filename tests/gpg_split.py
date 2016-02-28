#!/usr/bin/python
# vim: fileencoding=utf-8

#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2016 Marek Marczykowski-Górecki
#                                       <marmarek@invisiblethingslab.com>
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

import qubes.tests

class GpgSplitMixin(qubes.tests.SystemTestsMixin):
    def setUp(self):
        super(GpgSplitMixin, self).setUp()
        self.backend = self.qc.add_new_vm("QubesAppVm",
            name=self.make_vm_name('backend'),
            template=self.qc.get_vm_by_name(self.template))
        self.backend.create_on_disk(verbose=False)

        self.frontend = self.qc.add_new_vm("QubesAppVm",
            name=self.make_vm_name('frontend'),
            template=self.qc.get_vm_by_name(self.template))
        self.frontend.create_on_disk(verbose=False)

        self.save_and_reload_db()
        self.qc.unlock_db()
        self.backend = self.qc[self.backend.qid]
        self.frontend = self.qc[self.frontend.qid]
        self.backend.start()
        if self.backend.run('ls /etc/qubes-rpc/qubes.Gpg', wait=True) != 0:
            self.skipTest('gpg-split not installed')
        p = self.backend.run('gpg --gen-key --batch', passio_popen=True)
        p.stdin.write('''
Key-Type: RSA
Key-Length: 1024
Key-Usage: sign encrypt
Name-Real: Qubes test
Name-Email: user@localhost
Expire-Date: 0
%commit
        ''')
        p.stdin.close()
        # discard stdout
        p.stdout.read()
        p.wait()
        assert p.returncode == 0, 'key generation failed'

        # fake confirmation
        self.backend.run(
            'touch /var/run/qubes-gpg-split/stat.{}'.format(self.frontend.name))

        self.frontend.start()
        p = self.frontend.run('tee /rw/config/gpg-split-domain',
            passio_popen=True, user='root')
        p.stdin.write(self.backend.name)
        p.stdin.close()
        p.wait()

        with open('/etc/qubes-rpc/policy/qubes.Gpg', 'r+') as policy:
            policy_rules = policy.readlines()
            policy_rules.insert(0,
                "{} {} allow\n".format(self.frontend.name, self.backend.name))
            policy.truncate(0)
            policy.seek(0)
            policy.write(''.join(policy_rules))

    def tearDown(self):
        with open('/etc/qubes-rpc/policy/qubes.Gpg', 'r+') as policy:
            policy_rules = policy.readlines()
            try:
                policy_rules.remove(
                    "{} {} allow\n".format(self.frontend.name,
                                           self.backend.name))
                policy.truncate(0)
                policy.seek(0)
                policy.write(''.join(policy_rules))
            except ValueError:
                pass
        super(GpgSplitMixin, self).tearDown()

class TC_00_DirectMixin(GpgSplitMixin):
    def test_000_version(self):
        cmd = 'qubes-gpg-client-wrapper --version'
        p = self.frontend.run(cmd, wait=True)
        self.assertEquals(p, 0, '{} failed'.format(cmd))

    def test_010_list_keys(self):
        cmd = 'qubes-gpg-client-wrapper --list-keys'
        p = self.frontend.run(cmd, passio_popen=True)
        keys = p.stdout.read()
        p.wait()
        self.assertEquals(p.returncode, 0, '{} failed'.format(cmd))
        self.assertIn("Qubes test", keys)

    def test_020_export_secret_key_deny(self):
        # TODO check if backend really deny such operation, here it is denied
        # by the frontend
        cmd = 'qubes-gpg-client-wrapper -a --export-secret-keys user@localhost'
        p = self.frontend.run(cmd, passio_popen=True)
        keys = p.stdout.read()
        p.wait()
        self.assertNotEquals(p.returncode, 0,
            '{} succeeded unexpectedly'.format(cmd))
        self.assertEquals(keys, '')

    def test_030_sign_verify(self):
        msg = "Test message"
        cmd = 'qubes-gpg-client-wrapper -a --sign'
        p = self.frontend.run(cmd, passio_popen=True)
        p.stdin.write(msg)
        p.stdin.close()
        signature = p.stdout.read()
        p.wait()
        self.assertEquals(p.returncode, 0, '{} failed'.format(cmd))
        self.assertNotEquals('', signature)

        # verify first through gpg-split
        cmd = 'qubes-gpg-client-wrapper'
        p = self.frontend.run(cmd, passio_popen=True, passio_stderr=True)
        p.stdin.write(signature)
        p.stdin.close()
        decoded_msg = p.stdout.read()
        verification_result = p.stderr.read()
        p.wait()
        self.assertEquals(p.returncode, 0, '{} failed'.format(cmd))
        self.assertEquals(decoded_msg, msg)
        self.assertIn('\ngpg: Good signature from', verification_result)

        # verify in frontend directly
        cmd = 'gpg -a --export user@localhost'
        p = self.backend.run(cmd, passio_popen=True, passio_stderr=True)
        (pubkey, stderr) = p.communicate()
        self.assertEquals(p.returncode, 0,
            '{} failed: {}'.format(cmd, stderr))
        cmd = 'gpg --import'
        p = self.frontend.run(cmd, passio_popen=True, passio_stderr=True)
        (stdout, stderr) = p.communicate(pubkey)
        self.assertEquals(p.returncode, 0,
            '{} failed: {}{}'.format(cmd, stdout, stderr))
        cmd = "gpg"
        p = self.frontend.run(cmd, passio_popen=True, passio_stderr=True)
        p.stdin.write(signature)
        p.stdin.close()
        decoded_msg = p.stdout.read()
        verification_result = p.stderr.read()
        p.wait()
        self.assertEquals(p.returncode, 0,
            '{} failed: {}'.format(cmd, verification_result))
        self.assertEquals(decoded_msg, msg)
        self.assertIn('\ngpg: Good signature from', verification_result)

    def test_031_sign_verify_detached(self):
        msg = "Test message"
        self.frontend.run('echo "{}" > message'.format(msg), wait=True)
        cmd = 'qubes-gpg-client-wrapper -a -b --sign message > signature.asc'
        p = self.frontend.run(cmd, wait=True)
        self.assertEquals(p, 0, '{} failed'.format(cmd))

        # verify through gpg-split
        cmd = 'qubes-gpg-client-wrapper --verify signature.asc message'
        p = self.frontend.run(cmd, passio_popen=True, passio_stderr=True)
        decoded_msg = p.stdout.read()
        verification_result = p.stderr.read()
        p.wait()
        self.assertEquals(p.returncode, 0, '{} failed'.format(cmd))
        self.assertEquals(decoded_msg, '')
        self.assertIn('\ngpg: Good signature from', verification_result)

        # break the message and check again
        self.frontend.run('echo "{}" >> message'.format(msg), wait=True)
        cmd = 'qubes-gpg-client-wrapper --verify signature.asc message'
        p = self.frontend.run(cmd, passio_popen=True, passio_stderr=True)
        decoded_msg = p.stdout.read()
        verification_result = p.stderr.read()
        p.wait()
        self.assertNotEquals(p.returncode, 0,
            '{} unexpecedly succeeded'.format(cmd))
        self.assertEquals(decoded_msg, '')
        self.assertIn('\ngpg: BAD signature from', verification_result)

    # TODO:
    #  - encrypt/decrypt
    #  - large file (bigger than pipe/qrexec buffers)
    #  - qubes.GpgImportKey


def load_tests(loader, tests, pattern):
    try:
        qc = qubes.qubes.QubesVmCollection()
        qc.lock_db_for_reading()
        qc.load()
        qc.unlock_db()
        templates = [vm.name for vm in qc.values() if
                     isinstance(vm, qubes.qubes.QubesTemplateVm)]
    except OSError:
        templates = []
    for template in templates:
        tests.addTests(loader.loadTestsFromTestCase(
            type(
                'TC_00_Direct_' + template,
                (TC_00_DirectMixin, qubes.tests.QubesTestCase),
                {'template': template})))
    return tests
