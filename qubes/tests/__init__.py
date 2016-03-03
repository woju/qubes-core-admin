#!/usr/bin/python2 -O
# vim: fileencoding=utf-8
# pylint: disable=invalid-name

#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2014-2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2014-2015
#                   Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
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

import collections
import multiprocessing
import logging
import os
import shutil
import subprocess
import sys
import traceback
import unittest

import lxml.etree
import time

import qubes.config
import qubes.events

XMLPATH = '/var/lib/qubes/qubes-test.xml'
CLASS_XMLPATH = '/var/lib/qubes/qubes-class-test.xml'
TEMPLATE = 'fedora-23'
VMPREFIX = 'test-inst-'
CLSVMPREFIX = 'test-cls-'


#: :py:obj:`True` if running in dom0, :py:obj:`False` otherwise
in_dom0 = False

#: :py:obj:`False` if outside of git repo,
#: path to root of the directory otherwise
in_git = False

try:
    import libvirt
    libvirt.openReadOnly(qubes.config.defaults['libvirt_uri']).close()
    in_dom0 = True
except libvirt.libvirtError:
    pass

try:
    in_git = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel']).strip()
    qubes.log.LOGPATH = '/tmp'
    qubes.log.LOGFILE = '/tmp/qubes.log'
except subprocess.CalledProcessError:
    # git returned nonzero, we are outside git repo
    pass
except OSError:
    # command not found; let's assume we're outside
    pass


def skipUnlessDom0(test_item):
    '''Decorator that skips test outside dom0.

    Some tests (especially integration tests) have to be run in more or less
    working dom0. This is checked by connecting to libvirt.
    '''

    return unittest.skipUnless(in_dom0, 'outside dom0')(test_item)


def skipUnlessGit(test_item):
    '''Decorator that skips test outside git repo.

    There are very few tests that an be run only in git. One example is
    correctness of example code that won't get included in RPM.
    '''

    return unittest.skipUnless(in_git, 'outside git tree')(test_item)


class TestEmitter(qubes.events.Emitter):
    '''Dummy event emitter which records events fired on it.

    Events are counted in :py:attr:`fired_events` attribute, which is
    :py:class:`collections.Counter` instance. For each event, ``(event, args,
    kwargs)`` object is counted. *event* is event name (a string), *args* is
    tuple with positional arguments and *kwargs* is sorted tuple of items from
    keyword arguments.

    >>> emitter = TestEmitter()
    >>> emitter.fired_events
    Counter()
    >>> emitter.fire_event('event', 1, 2, 3, spam='eggs', foo='bar')
    >>> emitter.fired_events
    Counter({('event', (1, 2, 3), (('foo', 'bar'), ('spam', 'eggs'))): 1})
    '''

    def __init__(self, *args, **kwargs):
        super(TestEmitter, self).__init__(*args, **kwargs)

        #: :py:class:`collections.Counter` instance
        self.fired_events = collections.Counter()

    def fire_event(self, event, *args, **kwargs):
        super(TestEmitter, self).fire_event(event, *args, **kwargs)
        self.fired_events[(event, args, tuple(sorted(kwargs.items())))] += 1

    def fire_event_pre(self, event, *args, **kwargs):
        super(TestEmitter, self).fire_event_pre(event, *args, **kwargs)
        self.fired_events[(event, args, tuple(sorted(kwargs.items())))] += 1


class _AssertNotRaisesContext(object):
    """A context manager used to implement TestCase.assertNotRaises methods.

    Stolen from unittest and hacked. Regexp support stripped.
    """ # pylint: disable=too-few-public-methods

    def __init__(self, expected, test_case, expected_regexp=None):
        if expected_regexp is not None:
            raise NotImplementedError('expected_regexp is unsupported')

        self.expected = expected
        self.exception = None

        self.failureException = test_case.failureException


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            return True

        if issubclass(exc_type, self.expected):
            raise self.failureException(
                "{!r} raised, traceback:\n{!s}".format(
                    exc_value, ''.join(traceback.format_tb(tb))))
        else:
            # pass through
            return False

        self.exception = exc_value # store for later retrieval


class BeforeCleanExit(BaseException):
    '''Raised from :py:meth:`QubesTestCase.tearDown` when
    :py:attr:`qubes.tests.run.QubesDNCTestResult.do_not_clean` is set.'''
    pass


class QubesTestCase(unittest.TestCase):
    '''Base class for Qubes unit tests.
    '''

    def __init__(self, *args, **kwargs):
        super(QubesTestCase, self).__init__(*args, **kwargs)
        self.longMessage = True
        self.log = logging.getLogger('{}.{}.{}'.format(
            self.__class__.__module__,
            self.__class__.__name__,
            self._testMethodName))


    def __str__(self):
        return '{}/{}/{}'.format(
            '.'.join(self.__class__.__module__.split('.')[2:]),
            self.__class__.__name__,
            self._testMethodName)


    def tearDown(self):
        super(QubesTestCase, self).tearDown()

        result = self._resultForDoCleanups
        failed_test_cases = result.failures \
            + result.errors \
            + [(tc, None) for tc in result.unexpectedSuccesses]

        if getattr(result, 'do_not_clean', False) \
                and any(tc is self for tc, exc in failed_test_cases):
            raise BeforeCleanExit()


    def assertNotRaises(self, excClass, callableObj=None, *args, **kwargs):
        """Fail if an exception of class excClass is raised
           by callableObj when invoked with arguments args and keyword
           arguments kwargs. If a different type of exception is
           raised, it will not be caught, and the test case will be
           deemed to have suffered an error, exactly as for an
           unexpected exception.

           If called with callableObj omitted or None, will return a
           context object used like this::

                with self.assertRaises(SomeException):
                    do_something()

           The context manager keeps a reference to the exception as
           the 'exception' attribute. This allows you to inspect the
           exception after the assertion::

               with self.assertRaises(SomeException) as cm:
                   do_something()
               the_exception = cm.exception
               self.assertEqual(the_exception.error_code, 3)
        """
        context = _AssertNotRaisesContext(excClass, self)
        if callableObj is None:
            return context
        with context:
            callableObj(*args, **kwargs)


    def assertXMLEqual(self, xml1, xml2):
        '''Check for equality of two XML objects.

        :param xml1: first element
        :param xml2: second element
        :type xml1: :py:class:`lxml.etree._Element`
        :type xml2: :py:class:`lxml.etree._Element`
        '''  # pylint: disable=invalid-name

        self.assertEqual(xml1.tag, xml2.tag)
        self.assertEqual(xml1.text, xml2.text)
        self.assertItemsEqual(xml1.keys(), xml2.keys())
        for key in xml1.keys():
            self.assertEqual(xml1.get(key), xml2.get(key))


    def assertEventFired(self, emitter, event, args=None, kwargs=None):
        '''Check whether event was fired on given emitter and fail if it did
        not.

        :param emitter: emitter which is being checked
        :type emitter: :py:class:`TestEmitter`
        :param str event: event identifier
        :param list args: when given, all items must appear in args passed to \
            an event
        :param list kwargs: when given, all items must appear in kwargs passed \
            to an event
        '''

        for ev, ev_args, ev_kwargs in emitter.fired_events:
            if ev != event:
                continue
            if args is not None and any(i not in ev_args for i in args):
                continue
            if kwargs is not None and any(i not in ev_kwargs for i in kwargs):
                continue

            return

        self.fail('event {!r} did not fire on {!r}'.format(event, emitter))


    def assertEventNotFired(self, emitter, event, args=None, kwargs=None):
        '''Check whether event was fired on given emitter. Fail if it did.

        :param emitter: emitter which is being checked
        :type emitter: :py:class:`TestEmitter`
        :param str event: event identifier
        :param list args: when given, all items must appear in args passed to \
            an event
        :param list kwargs: when given, all items must appear in kwargs passed \
            to an event
        '''

        for ev, ev_args, ev_kwargs in emitter.fired_events:
            if ev != event:
                continue
            if args is not None and any(i not in ev_args for i in args):
                continue
            if kwargs is not None and any(i not in ev_kwargs for i in kwargs):
                continue

            self.fail('event {!r} did fire on {!r}'.format(event, emitter))

        return


    def assertXMLIsValid(self, xml, file=None, schema=None):
        '''Check whether given XML fulfills Relax NG schema.

        Schema can be given in a couple of ways:

        - As separate file. This is most common, and also the only way to
          handle file inclusion. Call with file name as second argument.

        - As string containing actual schema. Put that string in *schema*
          keyword argument.

        :param lxml.etree._Element xml: XML element instance to check
        :param str file: filename of Relax NG schema
        :param str schema: optional explicit schema string
        ''' # pylint: disable=redefined-builtin

        if schema is not None and file is None:
            relaxng = schema
            if isinstance(relaxng, str):
                relaxng = lxml.etree.XML(relaxng)
            # pylint: disable=protected-access
            if isinstance(relaxng, lxml.etree._Element):
                relaxng = lxml.etree.RelaxNG(relaxng)

        elif file is not None and schema is None:
            if not os.path.isabs(file):
                basedirs = ['/usr/share/doc/qubes/relaxng']
                if in_git:
                    basedirs.insert(0, os.path.join(in_git, 'relaxng'))
                for basedir in basedirs:
                    abspath = os.path.join(basedir, file)
                    if os.path.exists(abspath):
                        file = abspath
                        break
            relaxng = lxml.etree.RelaxNG(file=file)

        else:
            raise TypeError("There should be excactly one of 'file' and "
                "'schema' arguments specified.")

        # We have to be extra careful here in case someone messed up with
        # self.failureException. It should by default be AssertionError, just
        # what is spewed by RelaxNG(), but who knows what might happen.
        try:
            relaxng.assert_(xml)
        except self.failureException:
            raise
        except AssertionError as e:
            self.fail(str(e))

    @staticmethod
    def make_vm_name(name, class_teardown=False):
        if class_teardown:
            return CLSVMPREFIX + name
        else:
            return VMPREFIX + name


class SystemTestsMixin(object):
    """
    Mixin for integration tests. All the tests here should use self.app
    object and when need qubes.xml path - should use :py:data:`XMLPATH`
    defined in this file.
    Every VM created by test, must use :py:meth:`SystemTestsMixin.make_vm_name`
    for VM name.
    By default self.app represents empty collection, if anything is needed
    there from the real collection it can be imported from self.host_app in
    :py:meth:`SystemTestsMixin.setUp`. But *can not be modified* in any way -
    this include both changing attributes in
    :py:attr:`SystemTestsMixin.host_app` and modifying files of such imported
    VM. If test need to make some modification, it must clone the VM first.

    If some group of tests needs class-wide initialization, first of all the
    author should consider if it is really needed. But if so, setUpClass can
    be used to create Qubes(CLASS_XMLPATH) object and create/import required
    stuff there. VMs created in :py:meth:`TestCase.setUpClass` should
    use self.make_vm_name('...', class_teardown=True) for name creation.
    """
    # noinspection PyAttributeOutsideInit
    def setUp(self):
        if not in_dom0:
            self.skipTest('outside dom0')
        super(SystemTestsMixin, self).setUp()
        self.remove_test_vms()

        # need some information from the real qubes.xml - at least installed
        # templates; should not be used for testing, only to initialize self.app
        self.host_app = qubes.Qubes(os.path.join(
            qubes.config.system_path['qubes_base_dir'],
            qubes.config.system_path['qubes_store_filename']))
        if os.path.exists(CLASS_XMLPATH):
            shutil.copy(CLASS_XMLPATH, XMLPATH)
            self.app = qubes.Qubes(XMLPATH)
        else:
            self.app = qubes.Qubes.create_empty_store(qubes.tests.XMLPATH,
                default_kernel=self.host_app.default_kernel,
                clockvm=None,
                updatevm=None
            )
        os.environ['QUBES_XML_PATH'] = XMLPATH

    def init_default_template(self, template=None):
        if template is None:
            template = self.host_app.default_template
        elif isinstance(template, basestring):
            template = self.host_app.domains[template]

        template_vm = self.app.add_new_vm(qubes.vm.templatevm.TemplateVM,
            name=template.name,
            uuid=template.uuid,
            label='black')
        self.app.default_template = template_vm

    def reload_db(self):
        self.app = qubes.Qubes(qubes.tests.XMLPATH)

    def save_and_reload_db(self):
        self.app.save()
        self.reload_db()

    def tearDown(self):
        super(SystemTestsMixin, self).tearDown()
        self.remove_test_vms()
        # remove all references to VM objects, to release resources - most
        # importantly file descriptors; this object will live
        # during the whole test run, but all the file descriptors would be
        # depleted earlier
        del self.app
        del self.host_app
        for attr in dir(self):
            if isinstance(getattr(self, attr), qubes.vm.BaseVM):
                delattr(self, attr)

    @classmethod
    def tearDownClass(cls):
        super(SystemTestsMixin, cls).tearDownClass()
        if not in_dom0:
            return
        cls.remove_test_vms(xmlpath=CLASS_XMLPATH, prefix=CLSVMPREFIX)

    @classmethod
    def _remove_vm_qubes(cls, vm):
        vmname = vm.name
        app = vm.app

        try:
            # XXX .is_running() may throw libvirtError if undefined
            if vm.is_running():
                vm.force_shutdown()
        except: # pylint: disable=bare-except
            pass

        try:
            vm.remove_from_disk()
        except: # pylint: disable=bare-except
            pass

        try:
            vm.libvirt_domain.undefine()
        except (AttributeError, libvirt.libvirtError):
            pass

        del app.domains[vm]
        del vm

        app.save()
        del app

        # Now ensure it really went away. This may not have happened,
        # for example if vm.libvirt_domain malfunctioned.
        try:
            conn = libvirt.open(qubes.config.defaults['libvirt_uri'])
            dom = conn.lookupByName(vmname)
        except: # pylint: disable=bare-except
            pass
        else:
            cls._remove_vm_libvirt(dom)

        cls._remove_vm_disk(vmname)


    @staticmethod
    def _remove_vm_libvirt(dom):
        try:
            dom.destroy()
        except libvirt.libvirtError: # not running
            pass
        dom.undefine()


    @staticmethod
    def _remove_vm_disk(vmname):
        for dirspec in (
                'qubes_appvms_dir',
                'qubes_servicevms_dir',
                'qubes_templates_dir'):
            dirpath = os.path.join(qubes.config.system_path['qubes_base_dir'],
                qubes.config.system_path[dirspec], vmname)
            if os.path.exists(dirpath):
                if os.path.isdir(dirpath):
                    shutil.rmtree(dirpath)
                else:
                    os.unlink(dirpath)


    @classmethod
    def remove_vms(cls, vms):
        for vm in vms:
            cls._remove_vm_qubes(vm)


    @classmethod
    def remove_test_vms(cls, xmlpath=XMLPATH, prefix=VMPREFIX):
        '''Aggresively remove any domain that has name in testing namespace.

        .. warning::
            The test suite hereby claims any domain whose name starts with
            :py:data:`VMPREFIX` as fair game. This is needed to enforce sane
            test executing environment. If you have domains named ``test-*``,
            don't run the tests.
        '''

        # first, remove them Qubes-way
        if os.path.exists(xmlpath):
            try:
                cls.remove_vms(vm for vm in qubes.Qubes(xmlpath).domains
                    if vm.name.startswith(prefix))
            except qubes.exc.QubesException:
                # If qubes-test.xml is broken that much it doesn't even load,
                #  simply remove it. VMs will be cleaned up the hard way.
                # TODO logging?
                pass
            os.unlink(xmlpath)

        # now remove what was only in libvirt
        conn = libvirt.open(qubes.config.defaults['libvirt_uri'])
        for dom in conn.listAllDomains():
            if dom.name().startswith(prefix):
                cls._remove_vm_libvirt(dom)
        conn.close()

        # finally remove anything that is left on disk
        vmnames = set()
        for dirspec in (
                'qubes_appvms_dir',
                'qubes_servicevms_dir',
                'qubes_templates_dir'):
            dirpath = os.path.join(qubes.config.system_path['qubes_base_dir'],
                qubes.config.system_path[dirspec])
            for name in os.listdir(dirpath):
                if name.startswith(prefix):
                    vmnames.add(name)
        for vmname in vmnames:
            cls._remove_vm_disk(vmname)

    def wait_for_window(self, title, timeout=30, show=True):
        """
        Wait for a window with a given title. Depending on show parameter,
        it will wait for either window to show or to disappear.

        :param title: title of the window to wait for
        :param timeout: timeout of the operation, in seconds
        :param show: if True - wait for the window to be visible,
            otherwise - to not be visible
        :return: None
        """

        wait_count = 0
        while subprocess.call(['xdotool', 'search', '--name', title],
                              stdout=open(os.path.devnull, 'w'),
                              stderr=subprocess.STDOUT) == int(show):
            wait_count += 1
            if wait_count > timeout*10:
                self.fail("Timeout while waiting for {} window to {}".format(
                    title, "show" if show else "hide")
                )
            time.sleep(0.1)

    def enter_keys_in_window(self, title, keys):
        """
        Search for window with given title, then enter listed keys there.
        The function will wait for said window to appear.

        :param title: title of window
        :param keys: list of keys to enter, as for `xdotool key`
        :return: None
        """

        # 'xdotool search --sync' sometimes crashes on some race when
        # accessing window properties
        self.wait_for_window(title)
        command = ['xdotool', 'search', '--name', title,
                   'windowactivate',
                   'key'] + keys
        subprocess.check_call(command)

    def shutdown_and_wait(self, vm, timeout=60):
        vm.shutdown()
        while timeout > 0:
            if not vm.is_running():
                return
            time.sleep(1)
            timeout -= 1
        self.fail("Timeout while waiting for VM {} shutdown".format(vm.name))


# noinspection PyAttributeOutsideInit
class BackupTestsMixin(SystemTestsMixin):
    def setUp(self):
        super(BackupTestsMixin, self).setUp()
        self.init_default_template()
        self.error_detected = multiprocessing.Queue()
        self.verbose = False

        if self.verbose:
            print >>sys.stderr, "-> Creating backupvm"

        self.backupdir = os.path.join(os.environ["HOME"], "test-backup")
        if os.path.exists(self.backupdir):
            shutil.rmtree(self.backupdir)
        os.mkdir(self.backupdir)

    def tearDown(self):
        super(BackupTestsMixin, self).tearDown()
        shutil.rmtree(self.backupdir)

    def print_progress(self, progress):
        if self.verbose:
            print >> sys.stderr, "\r-> Backing up files: {0}%...".format(progress)

    def error_callback(self, message):
        self.error_detected.put(message)
        if self.verbose:
            print >> sys.stderr, "ERROR: {0}".format(message)

    def print_callback(self, msg):
        if self.verbose:
            print msg

    def fill_image(self, path, size=None, sparse=False):
        block_size = 4096

        if self.verbose:
            print >>sys.stderr, "-> Filling %s" % path
        f = open(path, 'w+')
        if size is None:
            f.seek(0, 2)
            size = f.tell()
        f.seek(0)

        for block_num in xrange(size/block_size):
            f.write('a' * block_size)
            if sparse:
                f.seek(block_size, 1)

        f.close()

    # NOTE: this was create_basic_vms
    def create_backup_vms(self):
        template = self.app.default_template

        vms = []
        vmname = self.make_vm_name('test-net')
        if self.verbose:
            print >>sys.stderr, "-> Creating %s" % vmname
        testnet = self.app.add_new_vm(qubes.vm.appvm.AppVM,
            name=vmname, template=template, provides_network=True)
        testnet.create_on_disk(verbose=self.verbose)
        vms.append(testnet)
        self.fill_image(testnet.private_img, 20*1024*1024)

        vmname = self.make_vm_name('test1')
        if self.verbose:
            print >>sys.stderr, "-> Creating %s" % vmname
        testvm1 = self.app.add_new_vm(qubes.vm.appvm.AppVM,
            name=vmname, template=template)
        testvm1.uses_default_netvm = False
        testvm1.netvm = testnet
        testvm1.create_on_disk(verbose=self.verbose)
        vms.append(testvm1)
        self.fill_image(testvm1.private_img, 100*1024*1024)

        vmname = self.make_vm_name('testhvm1')
        if self.verbose:
            print >>sys.stderr, "-> Creating %s" % vmname
        testvm2 = self.app.add_new_vm(qubes.vm.appvm.AppVM, name=vmname,
            hvm=True)
        testvm2.create_on_disk(verbose=self.verbose)
        self.fill_image(testvm2.root_img, 1024*1024*1024, True)
        vms.append(testvm2)

        self.app.save()

        return vms

    def make_backup(self, vms, prepare_kwargs=dict(), do_kwargs=dict(),
                    target=None, expect_failure=False):
        # XXX: bakup_prepare and backup_do don't support host_collection
        # self.qc.unlock_db()
        if target is None:
            target = self.backupdir
        try:
            files_to_backup = \
                qubes.backup.backup_prepare(vms,
                                      print_callback=self.print_callback,
                                      **prepare_kwargs)
        except qubes.qubes.QubesException as e:
            if not expect_failure:
                self.fail("QubesException during backup_prepare: %s" % str(e))
            else:
                raise

        try:
            qubes.backup.backup_do(target, files_to_backup, "qubes",
                             progress_callback=self.print_progress,
                             **do_kwargs)
        except qubes.qubes.QubesException as e:
            if not expect_failure:
                self.fail("QubesException during backup_do: %s" % str(e))
            else:
                raise

        # FIXME why?
        self.reload_db()

    def restore_backup(self, source=None, appvm=None, options=None,
                       expect_errors=None):
        if source is None:
            backupfile = os.path.join(self.backupdir,
                                      sorted(os.listdir(self.backupdir))[-1])
        else:
            backupfile = source

        with self.assertNotRaises(qubes.qubes.QubesException):
            backup_info = qubes.backup.backup_restore_prepare(
                backupfile, "qubes",
                host_collection=self.app,
                print_callback=self.print_callback,
                appvm=appvm,
                options=options or {})

        if self.verbose:
            qubes.backup.backup_restore_print_summary(backup_info)

        with self.assertNotRaises(qubes.qubes.QubesException):
            qubes.backup.backup_restore_do(
                backup_info,
                host_collection=self.app,
                print_callback=self.print_callback if self.verbose else None,
                error_callback=self.error_callback)

        # maybe someone forgot to call .save()
        self.reload_db()

        errors = []
        if expect_errors is None:
            expect_errors = []
        while not self.error_detected.empty():
            current_error = self.error_detected.get()
            if any(map(current_error.startswith, expect_errors)):
                continue
            errors.append(current_error)
        self.assertTrue(len(errors) == 0,
                         "Error(s) detected during backup_restore_do: %s" %
                         '\n'.join(errors))
        if not appvm and not os.path.isdir(backupfile):
            os.unlink(backupfile)

    def create_sparse(self, path, size):
        f = open(path, "w")
        f.truncate(size)
        f.close()


def load_tests(loader, tests, pattern): # pylint: disable=unused-argument
    # discard any tests from this module, because it hosts base classes
    tests = unittest.TestSuite()

    for modname in (
            # unit tests
            'qubes.tests.events',
            'qubes.tests.init1',
            'qubes.tests.vm.init',
            'qubes.tests.vm.qubesvm',
            'qubes.tests.vm.adminvm',
            'qubes.tests.init2',
            'qubes.tests.tools',

            # integration tests
            'qubes.tests.int.basic',
            'qubes.tests.int.dom0_update',
#           'qubes.tests.network',
#           'qubes.tests.vm_qrexec_gui',
#           'qubes.tests.backup',
#           'qubes.tests.backupcompatibility',
#           'qubes.tests.regressions',

            # tool tests
            'qubes.tests.int.tools.qubes_create',
            'qubes.tests.int.tools.qvm_run',
            ):
        tests.addTests(loader.loadTestsFromName(modname))

    return tests
