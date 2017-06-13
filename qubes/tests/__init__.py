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

"""
.. warning::
    The test suite hereby claims any domain whose name starts with
    :py:data:`VMPREFIX` as fair game. This is needed to enforce sane
    test executing environment. If you have domains named ``test-*``,
    don't run the tests.
"""

import asyncio
import collections
import functools
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
import warnings
from distutils import spawn

import lxml.etree
import pkg_resources

import qubes.api
import qubes.api.admin
import qubes.backup
import qubes.config
import qubes.devices
import qubes.events
import qubes.exc
import qubes.vm.standalonevm

XMLPATH = '/var/lib/qubes/qubes-test.xml'
CLASS_XMLPATH = '/var/lib/qubes/qubes-class-test.xml'
TEMPLATE = 'fedora-23'
VMPREFIX = 'test-inst-'
CLSVMPREFIX = 'test-cls-'


if 'DEFAULT_LVM_POOL' in os.environ.keys():
    DEFAULT_LVM_POOL = os.environ['DEFAULT_LVM_POOL']
else:
    DEFAULT_LVM_POOL = 'qubes_dom0/pool00'


POOL_CONF = {'name': 'test-lvm',
             'driver': 'lvm_thin',
             'volume_group': DEFAULT_LVM_POOL.split('/')[0],
             'thin_pool': DEFAULT_LVM_POOL.split('/')[1]}

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
        ['git', 'rev-parse', '--show-toplevel']).decode().strip()
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
    >>> emitter.fire_event('event', spam='eggs', foo='bar')
    >>> emitter.fired_events
    Counter({('event', (1, 2, 3), (('foo', 'bar'), ('spam', 'eggs'))): 1})
    '''

    def __init__(self, *args, **kwargs):
        super(TestEmitter, self).__init__(*args, **kwargs)

        #: :py:class:`collections.Counter` instance
        self.fired_events = collections.Counter()

    def fire_event(self, event, **kwargs):
        effects = super(TestEmitter, self).fire_event(event, **kwargs)
        ev_kwargs = frozenset(
            (key,
                frozenset(value.items()) if isinstance(value, dict) else value)
            for key, value in kwargs.items()
        )
        self.fired_events[(event, ev_kwargs)] += 1
        return effects

    def fire_event_pre(self, event, **kwargs):
        effects = super(TestEmitter, self).fire_event_pre(event, **kwargs)
        ev_kwargs = frozenset(
            (key,
                frozenset(value.items()) if isinstance(value, dict) else value)
            for key, value in kwargs.items()
        )
        self.fired_events[(event, ev_kwargs)] += 1
        return effects

def expectedFailureIfTemplate(templates):
    """
    Decorator for marking specific test as expected to fail only for some
    templates. Template name is compared as substring, so 'whonix' will
    handle both 'whonix-ws' and 'whonix-gw'.
     templates can be either a single string, or an iterable
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            template = self.template
            if isinstance(templates, str):
                should_expect_fail = template in templates
            else:
                should_expect_fail = any([template in x for x in templates])
            if should_expect_fail:
                try:
                    func(self, *args, **kwargs)
                except Exception:
                    raise unittest.case._ExpectedFailure(sys.exc_info())
                raise unittest.case._UnexpectedSuccess()
            else:
                # Call directly:
                func(self, *args, **kwargs)
        return wrapper
    return decorator

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

class _QrexecPolicyContext(object):
    '''Context manager for SystemTestsMixin.qrexec_policy'''

    def __init__(self, service, source, destination, allow=True):
        try:
            source = source.name
        except AttributeError:
            pass

        try:
            destination = destination.name
        except AttributeError:
            pass

        self._filename = pathlib.Path('/etc/qubes-rpc/policy') / service
        self._rule = '{} {} {}\n'.format(source, destination,
            'allow' if allow else 'deny')
        self._did_create = False
        self._handle = None

    def load(self):
        if self._handle is None:
            try:
                self._handle = self._filename.open('r+')
            except FileNotFoundError:
                self._handle = self._filename.open('w+')
                self._did_create = True
        self._handle.seek(0)
        return self._handle.readlines()

    def save(self, rules):
        assert self._handle is not None
        self._handle.truncate(0)
        self._handle.seek(0)
        self._handle.write(''.join(rules))

    def close(self):
        assert self._handle is not None
        self._handle.close()
        self._handle = None

    def __enter__(self):
        rules = self.load()
        rules.insert(0, self._rule)
        self.save(self._rule)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if not self._did_create:
            try:
                rules = self.load()
                rules.remove(self._rule)
                self.save(rules)
            finally:
                self.close()
        else:
            self.close()
            os.unlink(self._filename)

class substitute_entry_points(object):
    '''Monkey-patch pkg_resources to substitute one group in iter_entry_points

    This is for testing plugins, like device classes.

    :param str group: The group that is to be overloaded.
    :param str tempgroup: The substitute group.

    Inside this context, if one iterates over entry points in overloaded group,
    the iteration actually happens over the other group.

    This context manager is stackable. To substitute more than one entry point
    group, just nest two contexts.
    ''' # pylint: disable=invalid-name

    def __init__(self, group, tempgroup):
        self.group = group
        self.tempgroup = tempgroup
        self._orig_iter_entry_points = None

    def _iter_entry_points(self, group, *args, **kwargs):
        if group == self.group:
            group = self.tempgroup
        return self._orig_iter_entry_points(group, *args, **kwargs)

    def __enter__(self):
        self._orig_iter_entry_points = pkg_resources.iter_entry_points
        pkg_resources.iter_entry_points = self._iter_entry_points
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pkg_resources.iter_entry_points = self._orig_iter_entry_points
        self._orig_iter_entry_points = None


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
        self.addTypeEqualityFunc(qubes.devices.DeviceManager,
            self.assertDevicesEqual)

        self.loop = None


    def __str__(self):
        return '{}/{}/{}'.format(
            self.__class__.__module__,
            self.__class__.__name__,
            self._testMethodName)


    def setUp(self):
        super().setUp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        super(QubesTestCase, self).tearDown()

        # The loop, when closing, throws a warning if there is
        # some unfinished bussiness. Let's catch that.
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            self.loop.close()

        # TODO: find better way in py3
        try:
            result = self._outcome.result
        except:
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
        self.assertCountEqual(xml1.keys(), xml2.keys())
        for key in xml1.keys():
            self.assertEqual(xml1.get(key), xml2.get(key))

    def assertDevicesEqual(self, devices1, devices2, msg=None):
        self.assertEqual(devices1.keys(), devices2.keys(), msg)
        for dev_class in devices1.keys():
            self.assertEqual(
                [str(dev) for dev in devices1[dev_class]],
                [str(dev) for dev in devices2[dev_class]],
                "Devices of class {} differs{}".format(
                    dev_class, (": " + msg) if msg else "")
            )

    def assertEventFired(self, subject, event, kwargs=None):
        '''Check whether event was fired on given emitter and fail if it did
        not.

        :param subject: emitter which is being checked
        :type emitter: :py:class:`TestEmitter`
        :param str event: event identifier
        :param list kwargs: when given, all items must appear in kwargs passed \
            to an event
        '''

        will_not_match = object()
        for ev, ev_kwargs in subject.fired_events:
            if ev != event:
                continue
            if kwargs is not None:
                ev_kwargs = dict(ev_kwargs)
                if any(ev_kwargs.get(k, will_not_match) != v
                        for k, v in kwargs.items()):
                    continue

            return

        self.fail('event {!r} {}did not fire on {!r}'.format(
            event, ('' if kwargs is None else '{!r} '.format(kwargs)), subject))


    def assertEventNotFired(self, subject, event, kwargs=None):
        '''Check whether event was fired on given emitter. Fail if it did.

        :param subject: emitter which is being checked
        :type emitter: :py:class:`TestEmitter`
        :param str event: event identifier
        :param list kwargs: when given, all items must appear in kwargs passed \
            to an event
        '''

        will_not_match = object()
        for ev, ev_kwargs in subject.fired_events:
            if ev != event:
                continue
            if kwargs is not None:
                ev_kwargs = dict(ev_kwargs)
                if any(ev_kwargs.get(k, will_not_match) != v
                        for k, v in kwargs.items()):
                    continue

            self.fail('event {!r} {}did fire on {!r}'.format(
                event,
                ('' if kwargs is None else '{!r} '.format(kwargs)),
                subject))

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

        self.qrexec_policy_server = self.loop.run_until_complete(
            qubes.api.create_server(
                qubes.api.internal.QUBESD_INTERNAL_SOCK,
                qubes.api.internal.QubesInternalAPI,
                app=self.app,
                debug=True))

    def init_default_template(self, template=None):
        if template is None:
            template = self.host_app.default_template
        elif isinstance(template, str):
            template = self.host_app.domains[template]

        used_pools = [vol.pool for vol in template.volumes.values()]

        for pool in used_pools:
            if pool in self.app.pools:
                continue
            self.app.add_pool(**self.host_app.pools[pool].config)

        template_vm = self.app.add_new_vm(qubes.vm.templatevm.TemplateVM,
            name=template.name,
            uuid=template.uuid,
            label='black')
        for name, volume in template_vm.volumes.items():
            if volume.pool != template.volumes[name].pool:
                template_vm.storage.init_volume(name,
                    template.volumes[name].config)
        self.app.default_template = template_vm

    def init_networking(self):
        if not self.app.default_template:
            self.skipTest('Default template required for testing networking')
        default_netvm = self.host_app.default_netvm
        # if testing Whonix Workstation based VMs, try to use sys-whonix instead
        if self.app.default_template.name.startswith('whonix-ws'):
            if 'sys-whonix' in self.host_app.domains:
                default_netvm = self.host_app.domains['sys-whonix']
        if default_netvm is None:
            self.skipTest('Default netvm required')
        if not default_netvm.is_running():
            self.skipTest('VM {} required to be running'.format(
                default_netvm.name))
        # Add NetVM stub to qubes-test.xml matching the one on host.
        # Keeping 'qid' the same is critical because IP addresses are
        # calculated from it.
        # Intentionally don't copy template (use default), as it may be based
        #  on a different one than actually testing.
        netvm_clone = self.app.add_new_vm(default_netvm.__class__,
            qid=default_netvm.qid,
            name=default_netvm.name,
            uuid=default_netvm.uuid,
            label=default_netvm.label,
            provides_network=True
        )
        self.app.default_netvm = netvm_clone


    def _find_pool(self, volume_group, thin_pool):
        ''' Returns the pool matching the specified ``volume_group`` &
            ``thin_pool``, or None.
        '''
        pools = [p for p in self.app.pools
                 if issubclass(p.__class__, qubes.storage.lvm.ThinPool)]
        for pool in pools:
            if pool.volume_group == volume_group \
                    and pool.thin_pool == thin_pool:
                return pool
        return None

    def init_lvm_pool(self):
        volume_group, thin_pool = DEFAULT_LVM_POOL.split('/', 1)
        path = "/dev/mapper/{!s}-{!s}".format(volume_group, thin_pool)
        if not os.path.exists(path):
            self.skipTest('LVM thin pool {!r} does not exist'.
                format(DEFAULT_LVM_POOL))
        self.pool = self._find_pool(volume_group, thin_pool)
        if not self.pool:
            self.pool = self.app.add_pool(**POOL_CONF)
            self.created_pool = True

    def reload_db(self):
        self.app = qubes.Qubes(qubes.tests.XMLPATH)

    def save_and_reload_db(self):
        self.app.save()
        self.reload_db()

    def tearDown(self):
        # close the server before super(), because that might close the loop
        for sock in self.qrexec_policy_server.sockets:
            os.unlink(sock.getsockname())
        self.qrexec_policy_server.close()
        self.loop.run_until_complete(self.qrexec_policy_server.wait_closed())

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
                vm.kill()
        except: # pylint: disable=bare-except
            pass

        try:
            vm.remove_from_disk()
        except: # pylint: disable=bare-except
            pass

        del app.domains[vm.qid]
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

    @staticmethod
    def _remove_vm_disk_lvm(prefix=VMPREFIX):
        ''' Remove LVM volumes with given prefix

        This is "a bit" drastic, as it removes volumes regardless of volume
        group, thin pool etc. But we assume no important data on test system.
        '''
        try:
            volumes = subprocess.check_output(
                ['sudo', 'lvs', '--noheadings', '-o', 'vg_name,name',
                    '--separator', '/']).decode()
            if ('/' + prefix) not in volumes:
                return
            subprocess.check_call(['sudo', 'lvremove', '-f'] +
                [vol.strip() for vol in volumes.splitlines()
                    if ('/' + prefix) in vol],
                stdout=open(os.devnull, 'w'))
        except subprocess.CalledProcessError:
            pass

    @classmethod
    def remove_vms(cls, vms):
        for vm in vms:
            cls._remove_vm_qubes(vm)


    @classmethod
    def remove_test_vms(cls, xmlpath=XMLPATH, prefix=VMPREFIX):
        '''Aggresively remove any domain that has name in testing namespace.
        '''

        # first, remove them Qubes-way
        if os.path.exists(xmlpath):
            try:
                cls.remove_vms(vm for vm in qubes.Qubes(xmlpath).domains
                    if vm.name.startswith(prefix))
            except (qubes.exc.QubesException, lxml.etree.XMLSyntaxError):
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
        cls._remove_vm_disk_lvm(prefix)

    def qrexec_policy(self, service, source, destination, allow=True):
        """
        Allow qrexec calls for duration of the test
        :param service: service name
        :param source: source VM name
        :param destination: destination VM name
        :return:
        """

        return _QrexecPolicyContext(service, source, destination, allow=allow)

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
                stdout=open(os.path.devnull, 'w'), stderr=subprocess.STDOUT) \
                    == int(show):
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
                   'windowactivate', '--sync',
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

    def prepare_hvm_system_linux(self, vm, init_script, extra_files=None):
        if not os.path.exists('/usr/lib/grub/i386-pc'):
            self.skipTest('grub2 not installed')
        if not spawn.find_executable('grub2-install'):
            self.skipTest('grub2-tools not installed')
        if not spawn.find_executable('dracut'):
            self.skipTest('dracut not installed')
        # create a single partition
        p = subprocess.Popen(['sfdisk', '-q', '-L', vm.storage.root_img],
            stdin=subprocess.PIPE,
            stdout=open(os.devnull, 'w'),
            stderr=subprocess.STDOUT)
        p.communicate('2048,\n')
        assert p.returncode == 0, 'sfdisk failed'
        # TODO: check if root_img is really file, not already block device
        p = subprocess.Popen(['sudo', 'losetup', '-f', '-P', '--show',
            vm.storage.root_img], stdout=subprocess.PIPE)
        (loopdev, _) = p.communicate()
        loopdev = loopdev.strip()
        looppart = loopdev + 'p1'
        assert p.returncode == 0, 'losetup failed'
        subprocess.check_call(['sudo', 'mkfs.ext2', '-q', '-F', looppart])
        mountpoint = tempfile.mkdtemp()
        subprocess.check_call(['sudo', 'mount', looppart, mountpoint])
        try:
            subprocess.check_call(['sudo', 'grub2-install',
                '--target', 'i386-pc',
                '--modules', 'part_msdos ext2',
                '--boot-directory', mountpoint, loopdev],
                stderr=open(os.devnull, 'w')
            )
            grub_cfg = '{}/grub2/grub.cfg'.format(mountpoint)
            subprocess.check_call(
                ['sudo', 'chown', '-R', os.getlogin(), mountpoint])
            with open(grub_cfg, 'w') as f:
                f.write(
                    "set timeout=1\n"
                    "menuentry 'Default' {\n"
                    "  linux /vmlinuz root=/dev/xvda1 "
                    "rd.driver.blacklist=bochs_drm "
                    "rd.driver.blacklist=uhci_hcd console=hvc0\n"
                    "  initrd /initrd\n"
                    "}"
                )
            p = subprocess.Popen(['uname', '-r'], stdout=subprocess.PIPE)
            (kernel_version, _) = p.communicate()
            kernel_version = kernel_version.strip()
            kernel = '/boot/vmlinuz-{}'.format(kernel_version)
            shutil.copy(kernel, os.path.join(mountpoint, 'vmlinuz'))
            init_path = os.path.join(mountpoint, 'init')
            with open(init_path, 'w') as f:
                f.write(init_script)
            os.chmod(init_path, 0o755)
            dracut_args = [
                '--kver', kernel_version,
                '--include', init_path,
                '/usr/lib/dracut/hooks/pre-pivot/initscript.sh',
                '--no-hostonly', '--nolvmconf', '--nomdadmconf',
            ]
            if extra_files:
                dracut_args += ['--install', ' '.join(extra_files)]
            subprocess.check_call(
                ['dracut'] + dracut_args + [os.path.join(mountpoint,
                    'initrd')],
                stderr=open(os.devnull, 'w')
            )
        finally:
            subprocess.check_call(['sudo', 'umount', mountpoint])
            shutil.rmtree(mountpoint)
            subprocess.check_call(['sudo', 'losetup', '-d', loopdev])


def load_tests(loader, tests, pattern): # pylint: disable=unused-argument
    # discard any tests from this module, because it hosts base classes
    tests = unittest.TestSuite()

    for modname in (
            # unit tests
            'qubes.tests.events',
            'qubes.tests.devices',
            'qubes.tests.devices_block',
            'qubes.tests.firewall',
            'qubes.tests.init',
            'qubes.tests.vm.init',
            'qubes.tests.storage',
            'qubes.tests.storage_file',
            'qubes.tests.storage_lvm',
            'qubes.tests.storage_kernels',
            'qubes.tests.ext',
            'qubes.tests.vm.qubesvm',
            'qubes.tests.vm.mix.net',
            'qubes.tests.vm.adminvm',
            'qubes.tests.vm.appvm',
            'qubes.tests.app',
            'qubes.tests.tarwriter',
            'qubes.tests.api_admin',
            'qubes.tests.api_misc',
            'qubespolicy.tests',
            'qubes.tests.tools.qubesd',
            ):
        tests.addTests(loader.loadTestsFromName(modname))

    # GTK/Glib is way too old there
    if 'TRAVIS' not in os.environ:
        for modname in (
                'qubespolicy.tests.gtkhelpers',
                'qubespolicy.tests.rpcconfirmation',
                ):
            tests.addTests(loader.loadTestsFromName(modname))

    tests.addTests(loader.discover(
        os.path.join(os.path.dirname(__file__), 'tools')))

    if not in_dom0:
        return tests

    for modname in (
            # integration tests
            'qubes.tests.integ.basic',
            'qubes.tests.integ.storage',
            'qubes.tests.integ.devices_pci',
            'qubes.tests.integ.dom0_update',
            'qubes.tests.integ.network',
            'qubes.tests.integ.dispvm',
            'qubes.tests.integ.vm_qrexec_gui',
            'qubes.tests.integ.backup',
            'qubes.tests.integ.backupcompatibility',
#           'qubes.tests.regressions',

            # external modules
#           'qubes.tests.extra',
            ):
        tests.addTests(loader.loadTestsFromName(modname))

    return tests
