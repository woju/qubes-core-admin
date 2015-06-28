#!/usr/bin/python2
#
# The Qubes OS Project, http://www.qubes-os.org
#
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

from __future__ import absolute_import

import os
import os.path
import subprocess
import sys
import re

from qubes.storage import QubesVmStorage
from qubes.qubes import QubesException, vm_files

class QubesXenVmStorage(QubesVmStorage):
    """
    Class for VM storage of Xen VMs.
    """

    def __init__(self, vm, **kwargs):
        super(QubesXenVmStorage, self).__init__(vm, **kwargs)

        self.root_dev = "xvda"
        self.private_dev = "xvdb"
        self.volatile_dev = "xvdc"
        self.modules_dev = "xvdd"

        if self.vm.is_template():
            self.rootcow_img = os.path.join(self.vmdir, vm_files["rootcow_img"])
        else:
            self.rootcow_img = None

    def _format_disk_dev(self, path, script, vdev, rw=True, type="disk", domain=None):
        if path is None:
            return ''
        if rw:
            perm = 'w'
        else:
            perm = 'r'
        if script:
            result = "'script:%s:%s,%s,%s'" % (script, path, vdev, perm)
        else:
            result = "'phy:%s,%s,%s'" % (path, vdev, perm)
	return result+','

    def _get_rootdev(self):
        if self.vm.is_template():
            return self._format_disk_dev(
                    "{dir}/root.img:{dir}/root-cow.img".format(
                        dir=self.vmdir),
                    "origin", self.root_dev, True)
        elif self.vm.template:
            return self._format_disk_dev(
                    "{dir}/root.img:{dir}/root-cow.img".format(
                        dir=self.vm.template.dir_path),
                    "snapshot", self.root_dev, False)
        else:
            return self._format_disk_dev(
                    "{dir}/root.img".format(dir=self.vmdir),
                    "file", self.root_dev, True)

    def _get_privatedev(self):
        return self._format_disk_dev(self.private_img, 'file', self.private_dev, True)

    def _get_volatiledev(self):
        return self._format_disk_dev(self.volatile_img, 'file', self.volatile_dev, True)

    def get_config_params(self):
        args = {}
        args['rootdev'] = self._get_rootdev()
        args['privatedev'] = self._get_privatedev()
        args['volatiledev'] = self._get_volatiledev()
        if self.modules_img is not None:
            args['otherdevs'] = \
                    self._format_disk_dev(self.modules_img,
                            "file", self.modules_dev, self.modules_img_rw)
        elif self.drive is not None:
            (drive_type, drive_domain, drive_path) = self.drive.split(":")
            if drive_domain.lower() == "dom0":
                drive_domain = None

            args['otherdevs'] = self._format_disk_dev(drive_path, "file",
                    self.modules_dev,
                    rw=True if drive_type == "disk" else False, type=drive_type, domain=drive_domain)
        else:
            args['otherdevs'] = ''

        return args

    def create_on_disk_private_img(self, verbose, source_template = None):
        if source_template:
            template_priv = source_template.private_img
            if verbose:
                print >> sys.stderr, "--> Copying the template's private image: {0}".\
                        format(template_priv)
            self._copy_file(template_priv, self.private_img)
        else:
            f_private = open (self.private_img, "a+b")
            f_private.truncate (self.private_img_size)
            f_private.close ()

    def create_on_disk_root_img(self, verbose, source_template = None):
        if source_template:
            if not self.vm.updateable:
                # just use template's disk
                return
            else:
                template_root = source_template.root_img
                if verbose:
                    print >> sys.stderr, "--> Copying the template's root image: {0}".\
                            format(template_root)

                self._copy_file(template_root, self.root_img)
        else:
            f_root = open (self.root_img, "a+b")
            f_root.truncate (self.root_img_size)
            f_root.close ()
        if self.vm.is_template():
            self.commit_template_changes()

    def rename(self, old_name, new_name):
        self.log.info("Renaming %s to %s " % (old_name, new_name))
        super(QubesXenVmStorage, self).rename(old_name, new_name)

        old_dirpath = os.path.join(os.path.dirname(self.vmdir), old_name)
        if self.rootcow_img:
            self.rootcow_img = self.rootcow_img.replace(old_dirpath,
                                                        self.vmdir)

    def resize_private_img(self, size):
        f_private = open (self.private_img, "a+b")
        f_private.truncate (size)
        f_private.close ()

        # find loop device if any
        p = subprocess.Popen (["sudo", "losetup", "--associated", self.private_img],
                stdout=subprocess.PIPE)
        result = p.communicate()
        m = re.match(r"^(/dev/loop\d+):\s", result[0])
        if m is not None:
            loop_dev = m.group(1)

            # resize loop device
            subprocess.check_call(["sudo", "losetup", "--set-capacity", loop_dev])

    def commit_template_changes(self):
        assert self.vm.is_template()
        # TODO: move rootcow_img to this class; the same for vm.is_outdated()
        if os.path.exists (self.rootcow_img):
           os.rename (self.rootcow_img, self.rootcow_img + '.old')

        old_umask = os.umask(002)
        f_cow = open (self.rootcow_img, "w")
        f_root = open (self.root_img, "r")
        f_root.seek(0, os.SEEK_END)
        f_cow.truncate (f_root.tell()) # make empty sparse file of the same size as root.img
        f_cow.close ()
        f_root.close()
        os.umask(old_umask)

