#!/usr/bin/python2
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2013  Marek Marczykowski <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#

import os
import os.path
import subprocess
import sys
import re
import shutil
import stat

from qubes.qubes import QubesVm,register_qubes_vm_class,vmm,dry_run
from qubes.qubes import system_path,defaults
from qubes.qubes import QubesException

system_path["config_template_hvm"] = '/usr/share/qubes/vm-template-hvm.xml'

defaults["hvm_disk_size"] = 20*1024*1024*1024
defaults["hvm_private_img_size"] = 2*1024*1024*1024
defaults["hvm_memory"] = 512


class QubesHVm(QubesVm):
    """
    A class that represents an HVM. A child of QubesVm.
    """

    # FIXME: logically should inherit after QubesAppVm, but none of its methods
    # are useful for HVM

    def get_attrs_config(self):
        attrs = super(QubesHVm, self).get_attrs_config()
        attrs.pop('kernel')
        attrs.pop('kernels_dir')
        attrs.pop('kernelopts')
        attrs.pop('uses_default_kernel')
        attrs.pop('uses_default_kernelopts')
        attrs['dir_path']['eval'] = 'value if value is not None else os.path.join(system_path["qubes_appvms_dir"], self.name)'
        attrs['config_file_template']['eval'] = 'system_path["config_template_hvm"]'
        attrs['drive'] = { 'save': 'str(self.drive)' }
        # Remove this two lines when HVM will get qmemman support
        attrs['maxmem'].pop('save')
        attrs['maxmem']['eval'] = 'self.memory'
        attrs['timezone'] = { 'default': 'localtime', 'save': 'str(self.timezone)' }
        attrs['qrexec_installed'] = { 'default': False, 'save': 'str(self.qrexec_installed)' }
        attrs['guiagent_installed'] = { 'default' : False, 'save': 'str(self.guiagent_installed)' }
        attrs['_start_guid_first']['eval'] = 'True'
        attrs['services']['default'] = "{'meminfo-writer': False}"

        # only standalone HVM supported for now
        attrs['template']['eval'] = 'None'
        attrs['memory']['default'] = defaults["hvm_memory"]

        return attrs

    def __init__(self, **kwargs):

        super(QubesHVm, self).__init__(**kwargs)

        # Default for meminfo-writer have changed to (correct) False in the
        # same version as introduction of guiagent_installed, so for older VMs
        # with wrong setting, change is based on 'guiagent_installed' presence
        if "guiagent_installed" not in kwargs and \
            (not 'xml_element' in kwargs or kwargs['xml_element'].get('guiagent_installed') is None):
            self.services['meminfo-writer'] = False

        # Disable qemu GUID if the user installed qubes gui agent
        if self.guiagent_installed:
            self._start_guid_first = False

        self.storage.volatile_img = None

    @property
    def type(self):
        return "HVM"

    def is_appvm(self):
        return True

    def get_clone_attrs(self):
        attrs = super(QubesHVm, self).get_clone_attrs()
        attrs.remove('kernel')
        attrs.remove('uses_default_kernel')
        attrs.remove('kernelopts')
        attrs.remove('uses_default_kernelopts')
        attrs += [ 'timezone' ]
        attrs += [ 'qrexec_installed' ]
        attrs += [ 'guiagent_installed' ]
        return attrs

    def create_on_disk(self, verbose, source_template = None):
        if dry_run:
            return

        # create empty disk
        self.storage.private_img_size = defaults["hvm_private_img_size"]
        self.storage.root_img_size = defaults["hvm_disk_size"]
        self.storage.create_on_disk(verbose, source_template)

        if verbose:
            print >> sys.stderr, "--> Creating icon symlink: {0} -> {1}".format(self.icon_path, self.label.icon_path)

        try:
            if hasattr(os, "symlink"):
                os.symlink (self.label.icon_path, self.icon_path)
            else:
                shutil.copy(self.label.icon_path, self.icon_path)
        except Exception as e:
            print >> sys.stderr, "WARNING: Failed to set VM icon: %s" % str(e)

        # fire hooks
        for hook in self.hooks_create_on_disk:
            hook(self, verbose, source_template=source_template)

    def get_disk_utilization_private_img(self):
        return 0

    def get_private_img_sz(self):
        return 0

    def resize_private_img(self, size):
        raise NotImplementedError("HVM has no private.img")

    def get_config_params(self):

        params = super(QubesHVm, self).get_config_params()

        self.storage.drive = self.drive
        params.update(self.storage.get_config_params())
        params['volatiledev'] = ''

        # Disable currently unused private.img - to be enabled when TemplateHVm done
        params['privatedev'] = ''

        if self.timezone.lower() == 'localtime':
             params['time_basis'] = 'localtime'
             params['timeoffset'] = '0'
        elif self.timezone.isdigit():
            params['time_basis'] = 'UTC'
            params['timeoffset'] = self.timezone
        else:
            print >>sys.stderr, "WARNING: invalid 'timezone' value: %s" % self.timezone
            params['time_basis'] = 'UTC'
            params['timeoffset'] = '0'
        return params

    def verify_files(self):
        if dry_run:
            return

        self.storage.verify_files()
        if not os.path.exists (self.private_img):
            print >>sys.stderr, "WARNING: Creating empty VM private image file: {0}".\
                format(self.private_img)
            self.storage.create_on_disk_private_img(verbose=False)

        # fire hooks
        for hook in self.hooks_verify_files:
            hook(self)

        return True

    def reset_volatile_storage(self, **kwargs):
        pass

    @property
    def vif(self):
        if self.xid < 0:
            return None
        if self.netvm is None:
            return None
        return "vif{0}.+".format(self.stubdom_xid)

    def run(self, command, **kwargs):
        if self.qrexec_installed:
            if 'gui' in kwargs and kwargs['gui']==False:
                command = "nogui:" + command
            return super(QubesHVm, self).run(command, **kwargs)
        else:
            raise QubesException("Needs qrexec agent installed in VM to use this function. See also qvm-prefs.")

    @property
    def stubdom_xid(self):
        if self.xid < 0:
            return -1

        stubdom_xid_str = vmm.xs.read('', '/local/domain/%d/image/device-model-domid' % self.xid)
        if stubdom_xid_str is not None:
            return int(stubdom_xid_str)
        else:
            return -1

    def start_guid(self, verbose = True, notify_function = None):
        # If user force the guiagent, start_guid will mimic a standard QubesVM
        if self.guiagent_installed:
            super(QubesHVm, self).start_guid(verbose, notify_function)
        else:
            if verbose:
                print >> sys.stderr, "--> Starting Qubes GUId..."

            retcode = subprocess.call ([system_path["qubes_guid_path"],
                "-d", str(self.stubdom_xid),
                "-t", str(self.xid),
                "-n", self.name,
                "-c", self.label.color,
                "-i", self.label.icon_path,
                "-l", str(self.label.index)])
            if (retcode != 0) :
                raise QubesException("Cannot start qubes-guid!")

    def start_qrexec_daemon(self, **kwargs):
        if self.qrexec_installed:
            super(QubesHVm, self).start_qrexec_daemon(**kwargs)

            if self._start_guid_first:
                if kwargs.get('verbose'):
                    print >> sys.stderr, "--> Waiting for user '%s' login..." % self.default_user

                self.wait_for_session(notify_function=kwargs.get('notify_function', None))

    def is_guid_running(self):
        # If user force the guiagent, is_guid_running will mimic a standard QubesVM
        if self.guiagent_installed:
            return super(QubesHVm, self).is_guid_running()
        else:
            xid = self.stubdom_xid
            if xid < 0:
                return False
            if not os.path.exists('/var/run/qubes/guid-running.%d' % xid):
                return False
            return True


register_qubes_vm_class(QubesHVm)
