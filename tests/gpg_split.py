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

class TC_10_ThunderbirdMixin(GpgSplitMixin):
    testing_library = '''
#!/usr/bin/python
from dogtail import tree
from dogtail.utils import run
from dogtail.predicate import GenericPredicate
from dogtail.config import config
import subprocess
import os
import shutil
import time

subject = 'Test message {}'.format(os.getpid())

config.actionDelay = 0.5
config.searchCutoffCount = 10

def run(cmd):
    env = os.environ.copy()
    env['GTK_MODULES'] = 'gail:atk-bridge'
    null = open(os.devnull, 'r+')
    subprocess.Popen([cmd], stdout=null, stdin=null, stderr=null, env=env)

def get_app():
    config.searchCutoffCount = 20
    tb = tree.root.application('Thunderbird|Icedove')
    config.searchCutoffCount = 10
    return tb

def skip_autoconf(tb):
    # Thunderbird flavor
    try:
        welcome = tb.childNamed('Welcome to .*')
        welcome.button(
            'I think I\\'ll configure my account later.').\
            doActionNamed('press')
    except tree.SearchError:
        pass
    config.searchCutoffCount = 5
    # Icedove flavor
    try:
        welcome = tb.childNamed('Mail Account Setup')
        welcome.button('Cancel').doActionNamed('press')
    except tree.SearchError:
        pass
    # if enigmail is already installed
    try:
        tb.dialog('Enigmail Setup Wizard').button('Cancel').\
            doActionNamed('press')
        tb.dialog('Enigmail Alert').button('Close').doActionNamed('press')
    except tree.SearchError:
        pass
    config.searchCutoffCount = 10

def skip_system_integration(tb):
    try:
        integration = tb.childNamed('System Integration')
        integration.childNamed('Always perform .*').doActionNamed('uncheck')
        integration.button('Skip Integration').doActionNamed('press')
    except tree.SearchError:
        pass

def open_account_setup(tb):
    edit = tb.menu('Edit')
    edit.doActionNamed('click')
    account_settings = edit.menuItem('Account Settings')
    account_settings.doActionNamed('click')

class TBEntry(GenericPredicate):
    def __init__(self, name):
        super(TBEntry, self).__init__(name=name, roleName='entry')

def add_local_account(tb):
    open_account_setup(tb)
    settings = tb.dialog('Account Settings')
    settings.button('Account Actions').doActionNamed('press')
    settings.menuItem('Add Other Account.*').doActionNamed('click')
    wizard = tb.dialog('Account Wizard')
    wizard.childNamed('Unix Mailspool (Movemail)').doActionNamed('select')
    wizard.button('Next').doActionNamed('press')
    wizard.findChild(TBEntry('Your Name:')).text = 'Test'
    wizard.findChild(TBEntry('Email Address:')).text = 'user@localhost'
    wizard.button('Next').doActionNamed('press')
    # outgoing server
    wizard.button('Next').doActionNamed('press')
    # account name
    wizard.button('Next').doActionNamed('press')
    # summary
    wizard.button('Finish').doActionNamed('press')

    # set outgoing server
    settings.childNamed('Outgoing Server (SMTP)').doActionNamed('activate')
    settings.button('Add.*').doActionNamed('press')
    add_server = tb.dialog('SMTP Server')
    add_server.findChild(TBEntry('Description:')).text = 'localhost'
    add_server.findChild(TBEntry('Server Name:')).text = 'localhost'
    add_server.findChild(TBEntry('Port:')).text = '8025'
    add_server.menuItem('No authentication').doActionNamed('click')
    add_server.button('OK').doActionNamed('press')
    settings.button('OK').doActionNamed('press')

def install_enigmail(tb):
    tools = tb.menu('Tools')
    tools.doActionNamed('click')
    tools.menuItem('Add-ons').doActionNamed('click')
    addons = tb.findChild(
        GenericPredicate(name='Add-ons Manager', roleName='embedded'))
    # check if already installed
    addons.findChild(
        GenericPredicate(name='Extensions', roleName='list item')).\
        doActionNamed('')
    config.searchCutoffCount = 1
    try:
        addons.childNamed('Enigmail.*')
    except tree.SearchError:
        pass
    else:
        # already installed
        return
    finally:
        config.searchCutoffCount = 10
    search = addons.findChild(
        GenericPredicate(name='Search all add-ons', roleName='section'))
    # search term
    search.children[0].text = 'enigmail'
    # saerch button
    search.children[1].doActionNamed('press')

    enigmail = addons.findChild(
        GenericPredicate(name='Enigmail .*', roleName='list item'))
    enigmail.button('Install').doActionNamed('press')
    addons.button('Restart now').doActionNamed('press')

    tree.doDelay(5)
    tb = get_app()
    skip_system_integration(tb)

    tb.dialog('Enigmail Setup Wizard').button('Cancel').doActionNamed('press')
    tb.dialog('Enigmail Alert').button('Close').doActionNamed('press')

def configure_enigmail_global(tb):
    tools = tb.menu('Tools')
    tools.doActionNamed('click')
    tools.menuItem('Add-ons').doActionNamed('click')
    addons = tb.findChild(
        GenericPredicate(name='Add-ons Manager', roleName='embedded'))
    addons.findChild(
        GenericPredicate(name='Extensions', roleName='list item')).\
        doActionNamed('')

    enigmail = addons.findChild(
        GenericPredicate(name='Enigmail .*', roleName='list item'))
    enigmail.button('Preferences').doActionNamed('press')

    enigmail_prefs = tb.dialog('Enigmail Preferences')
    # wait for dialog to really initialize, otherwise it may load defaults
    # over just set values
    time.sleep(1)
    try:
        enigmail_prefs.findChild(GenericPredicate(name='Override with',
            roleName='check box')).doActionNamed('check')
        enigmail_prefs.findChild(GenericPredicate(name='Override with',
            roleName='section')).children[
            0].text = '/usr/bin/qubes-gpg-client-wrapper'
    except tree.ActionNotSupported:
        pass

    enigmail_prefs.button('OK').doActionNamed('press')
    config.searchCutoffCount = 5
    try:
        agent_alert = tb.dialog('Enigmail Alert')
        if 'Cannot connect to gpg-agent' in agent_alert.description:
            agent_alert.childNamed('Do not show.*').doActionNamed('check')
            agent_alert.button('OK').doActionNamed('press')
        else:
            raise Exception('Unknown alert: {}'.format(agent_alert.description))
    except tree.SearchError:
        pass
    finally:
        config.searchCutoffCount = 10

def configure_enigmail_account(tb):
    open_account_setup(tb)
    settings = tb.dialog('Account Settings')
    # assume only one account...
    settings.childNamed('OpenPGP Security').doActionNamed('activate')
    try:
        settings.childNamed('Enable OpenPGP.*').doActionNamed('check')
    except tree.ActionNotSupported:
        pass
    settings.button('OK').doActionNamed('press')

def send_email(tb, sign=False, encrypt=False, inline=False):
    tb.findChild(GenericPredicate(roleName='page tab list')).children[
        0].doActionNamed('switch')
    write = tb.button('Write')
    write.doActionNamed('press')
    # write.menuItem('Message').doActionNamed('click')
    tb.button('Write').menuItem('Message').doActionNamed('click')
    compose = tb.findChild(GenericPredicate(name='Write: .*', roleName='frame'))
    to = compose.findChild(
        GenericPredicate(name='To:', roleName='autocomplete'))
    to.findChild(GenericPredicate(roleName='entry')).text = 'user@localhost'
    compose.findChild(TBEntry('Subject:')).text = subject
    compose.findChild(GenericPredicate(
        roleName='document frame')).text = 'This is test message'
    compose.button('Enigmail Encryption Info').doActionNamed('press')
    sign_encrypt = tb.dialog('Enigmail Encryption & Signing Settings')
    encrypt_checkbox = sign_encrypt.childNamed('Encrypt Message')
    if encrypt_checkbox.checked != encrypt:
        encrypt_checkbox.doActionNamed(encrypt_checkbox.actions.keys()[0])
    sign_checkbox = sign_encrypt.childNamed('Sign Message')
    if sign_checkbox.checked != sign:
        sign_checkbox.doActionNamed(sign_checkbox.actions.keys()[0])
    if inline:
        sign_encrypt.childNamed('Use Inline PGP').doActionNamed('select')
    else:
        sign_encrypt.childNamed('Use PGP/MIME').doActionNamed('select')
    sign_encrypt.button('OK').doActionNamed('press')
    compose.button('Send').doActionNamed('press')

def receive_message(tb, signed=False, encrypted=False):
    tb.findChild(GenericPredicate(name='user@localhost',
        roleName='table row')).doActionNamed('activate')
    tb.button('Get Messages').doActionNamed('press')
    tb.menuItem('Get All New Messages').doActionNamed('click')
    tb.findChild(
        GenericPredicate(name='Inbox.*', roleName='table row')).doActionNamed(
        'activate')
    tb.findChild(GenericPredicate(name='{}.*'.format(subject),
        roleName='table row')).doActionNamed('activate')
    msg = tb.findChild(GenericPredicate(roleName='document frame'))
    msg = tb.findChild(GenericPredicate(roleName='paragraph'))
    msg_body = msg.text
    print 'Message body: {}'.format(msg_body)
    assert msg_body.strip() == 'This is test message'
    #    if msg.children:
    #        msg_body = msg.children[0].text
    #    else:
    #        msg_body = msg.text
    config.searchCutoffCount = 5
    try:
        details = tb.button('Details')
        enigmail_status = details.parent.children[details.indexInParent - 1]
        print 'Enigmail status: {}'.format(enigmail_status.text)
        if signed:
            assert 'Good signature from' in enigmail_status.text
        if encrypted:
            assert 'Decrypted message' in enigmail_status.text
    except tree.SearchError:
        if signed or encrypted:
            raise
    finally:
        config.searchCutoffCount = 10

    # tb.button('Delete').doActionNamed('press')

def quit(tb):
    tb.button('AppMenu').doActionNamed('press')
    tb.menu('AppMenu').menuItem('Quit').doActionNamed('click')
'''

    smtp_server_script = '''
#!/usr/bin/python

from smtpd import SMTPServer
import asyncore
import mailbox

class LocalSMTPServer(SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data):
        msg = mailbox.Message(data)
        mbox = mailbox.mbox('/var/mail/user')
        mbox.lock()
        mbox.add(msg)
        mbox.close()

if __name__ == '__main__':
    LocalSMTPServer(('localhost', 8025), None)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
'''

    def setUp(self):
        super(TC_10_ThunderbirdMixin, self).setUp()
        if self.frontend.run('which thunderbird', wait=True) == 0:
            self.tb_name = 'thunderbird'
        elif self.frontend.run('which icedove', wait=True) == 0:
            self.tb_name = 'icedove'
        else:
            self.skipTest('Thunderbird not installed')
        if self.frontend.run(
                'python -c \'import dogtail,sys;'
                'sys.exit(dogtail.__version__ < "0.9.0")\'', wait=True) \
                != 0:
            self.skipTest('dogtail >= 0.9.0 testing framework not installed')

        p = self.frontend.run('gsettings set org.gnome.desktop.interface '
                              'toolkit-accessibility true', wait=True)
        assert p == 0, 'Failed to enable accessibility toolkit'
        p = self.frontend.run('cat > testing_library.py', passio_popen=True)
        p.stdin.write(self.testing_library)
        p.stdin.close()
        p.wait()
        assert p.returncode == 0

        p = self.frontend.run('cat > smtp_server.py', passio_popen=True)
        p.stdin.write(self.smtp_server_script)
        p.stdin.close()
        p.wait()
        assert p.returncode == 0

        # run as root to not deal with /var/mail permission issues
        self.frontend.run(
            'touch /var/mail/user; chown user /var/mail/user', user='root')
        self.frontend.run('python /home/user/smtp_server.py', user='root')

        p = self.frontend.run(
            'cat > script.py; PYTHONIOENCODING=utf-8 python script.py 2>&1',
            passio_popen=True)
        script = (
            'from testing_library import *\n'
            'run(\'{tb_name}\')\n'
            'tb = get_app()\n'
            'skip_autoconf(tb)\n'
            'add_local_account(tb)\n'
            'install_enigmail(tb)\n'
            'tb = get_app()\n'
            'configure_enigmail_global(tb)\n'
            'configure_enigmail_account(tb)\n'.format(tb_name=self.tb_name)
        )
        (stdout, _) = p.communicate(script)
        assert p.returncode == 0, 'Thunderbird setup failed: {}'.format(stdout)

    def test_000_send_receive_default(self):
        p = self.frontend.run(
            'cat > script.py; PYTHONIOENCODING=utf-8 python script.py 2>&1',
            passio_popen=True)
        script = (
            'from testing_library import *\n'
            'import time\n'
            'tb = get_app()\n'
            'send_email(tb, sign=True, encrypt=True)\n'
            'time.sleep(5)\n'
            'receive_message(tb, signed=True, encrypted=True)\n'
            'quit(tb)\n'
        )
        (stdout, _) = p.communicate(script)
        self.assertEquals(p.returncode, 0,
            'Thunderbird send/receive failed: {}'.format(stdout))

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

        tests.addTests(loader.loadTestsFromTestCase(
            type(
                'TC_10_Thunderbird_' + template,
                (TC_10_ThunderbirdMixin, qubes.tests.QubesTestCase),
                {'template': template})))
    return tests
