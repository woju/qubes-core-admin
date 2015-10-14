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

'''
Qubes OS exception hierarchy
'''

class QubesException(Exception):
    '''Exception that can be shown to the user'''
    pass


class QubesVMNotFoundError(QubesException, KeyError):
    '''Domain cannot be found in the system'''
    def __init__(self, vmname):
        super(QubesVMNotFoundError, self).__init__(
            'No such domain: {!r}'.format(vmname))
        self.vmname = vmname


class QubesVMError(QubesException):
    '''Some problem with domain state.'''
    def __init__(self, vm, msg):
        super(QubesVMError, self).__init__(msg)
        self.vm = vm


class QubesVMNotStartedError(QubesVMError):
    '''Domain is not started.

    This exception is thrown when machine is halted, but should be started
    (that is, either running or paused).
    '''
    def __init__(self, vm, msg=None):
        super(QubesVMNotStartedError, self).__init__(vm,
            msg or 'Domain is powered off: {!r}'.format(vm.name))


class QubesVMNotRunningError(QubesVMNotStartedError):
    '''Domain is not running.

    This exception is thrown when machine should be running but is either
    halted or paused.
    '''
    def __init__(self, vm, msg=None):
        super(QubesVMNotRunningError, self).__init__(vm,
            msg or 'Domain not running (either powered off or paused): {!r}' \
                .format(vm.name))


class QubesVMNotPausedError(QubesVMNotStartedError):
    '''Domain is not paused.

    This exception is thrown when machine should be paused, but is not.
    '''
    def __init__(self, vm, msg=None):
        super(QubesVMNotPausedError, self).__init__(vm,
            msg or 'Domain is not paused: {!r}'.format(vm.name))


class QubesVMNotSuspendedError(QubesVMError):
    '''Domain is not suspended.

    This exception is thrown when machine should be suspended but is either
    halted or running.
    '''
    def __init__(self, vm, msg=None):
        super(QubesVMNotSuspendedError, self).__init__(vm,
            msg or 'Domain is not suspended: {!r}'.format(vm.name))


class QubesVMNotHaltedError(QubesVMError):
    '''Domain is not halted.

    This exception is thrown when machine should be halted, but is not (either
    running or paused).
    '''
    def __init__(self, vm, msg=None):
        super(QubesVMNotHaltedError, self).__init__(vm,
            msg or 'Domain is not powered off: {!r}'.format(vm.name))


class QubesNoTemplateError(QubesVMError):
    '''Cannot start domain, because there is no template'''
    def __init__(self, vm, msg=None):
        super(QubesNoTemplateError, self).__init__(
            msg or 'Template for the domain {!r} not found'.format(vm.name))


class QubesValueError(QubesException, ValueError):
    '''Cannot set some value, because it is invalid, out of bounds, etc.'''
    pass


class QubesPropertyValueError(QubesValueError):
    '''Cannot set value of qubes.property, because user-supplied value is wrong.
    '''
    def __init__(self, holder, prop, value, msg=None):
        super(QubesPropertyValueError, self).__init__(
            msg or 'Invalid value {!r} for property {!r} of {!r}'.format(
                value, prop.__name__, holder))
        self.holder = holder
        self.prop = prop
        self.value = value


class QubesNotImplementedError(QubesException, NotImplementedError):
    '''Thrown at user when some feature is not implemented'''
    def __init__(self, msg=None):
        super(QubesNotImplementedError, self).__init__(
            msg or 'This feature is not available')


class BackupCancelledError(QubesException):
    '''Thrown at user when backup was manually cancelled'''
    def __init__(self, msg=None):
        super(BackupCancelledError, self).__init__(
            msg or 'Backup cancelled')


class QubesMemoryError(QubesException, MemoryError):
    '''Cannot start domain, because not enough memory is available'''
    def __init__(self, vm, msg=None):
        super(QubesMemoryError, self).__init__(
            msg or 'Not enough memory to start domain {!r}'.format(vm.name))
        self.vm = vm
