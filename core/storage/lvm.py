#!/usr/bin/python2
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015  Bahtiar Gadimov <bahtiar@gadimov.de>
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

import logging
import subprocess
import os
import shutil
import sys

from qubes.storage.xen import QubesXenVmStorage
from qubes.qubes import QubesException

VG = 'qubes_dom0'
LVM = '/dev/' + VG + '/'

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class QubesLvmVmStorage(QubesXenVmStorage):

    def __init__(self, vm, **kwargs):
        super(QubesLvmVmStorage, self).__init__(vm, **kwargs)
        self.private_img = LVM + vm.name + "-private"
        if self.vm.is_updateable():
            self.root_img = LVM + vm.name + "-root"
            

    def _get_privatedev(self):
        return "'phy:%s,%s,w'," % (self.private_img, self.private_dev)

    def _get_rootdev(self):
        if self.vm.is_updateable():
            return "'phy:%s,%s,w'," % (self.root_img, self.root_dev)
        else: # handle the the templates vms
            if self.vm.template and self.vm.template.storage_type == "lvm":
                removeLVM(self.root_img)
                snapshotLVM(self.vm.template.root_img, self.root_img)
                return "'phy:%s,%s,w'," % (self.root_img, self.root_dev)
            else:
                return super(QubesLvmVmStorage, self)._get_rootdev()

    def create_on_disk_private_img(self, verbose, source_template = None):
        self.log.info("Creating empty private img for %s" % self.vm.name)
        if source_template is not None:
            snapshotLVM(source_template.private_img, self.private_img)
        else:
            createEmptyImg(self.private_img, self.private_img_size)
        if self.vm.is_updateable():
            if source_template is not None:
                snapshotLVM(source_template.root_img, self.root_img)
            else:
                createEmptyImg(self.root_img, self.root_img_size)
            

    def verify_files(self):
        self.log.debug("Verifying files")
        if not os.path.exists (self.vmdir):
            self.log.error("VM directory doesn't exist: %s" % self.vmdir)
            raise QubesException (
                "VM directory doesn't exist: {0}".\
                format(self.vmdir))

        if self.root_img and not os.path.exists (self.root_img) and self.vm.is_updateable():
            self.log.error("VM root image doesn't exist: %s" % self.root_img)
            raise QubesException (
                "VM root image file doesn't exist: {0}".\
                format(self.root_img))

        if self.private_img and not os.path.exists (self.private_img):
            self.log.error("VM private image doesn't exist: %s" % self.private_img)
            raise QubesException (
                "VM private image file doesn't exist: {0}".\
                format(self.private_img))
        if self.modules_img is not None:
            if not os.path.exists(self.modules_img):
                self.log.error("VM modules image doesn't exist: %s" % self.modules_img)
                raise QubesException (
                        "VM kernel modules image does not exists: {0}".\
                                format(self.modules_img))


    def rename(self, old_name, new_name):
        self.log.debug("Renaming %s to %s " % (old_name, new_name))
        old_vmdir = self.vmdir
        new_vmdir = os.path.join(os.path.dirname(self.vmdir), new_name)
        os.rename(self.vmdir, new_vmdir)
        self.vmdir = new_vmdir
        if self.private_img:
            self.private_img = renameLVM(self.private_img, LVM + new_name + "-private")
        if self.root_img:
            self.root_img = self.root_img.replace(old_vmdir, new_vmdir)
        if self.volatile_img:
            self.volatile_img = self.volatile_img.replace(old_vmdir, new_vmdir)

    def remove_from_disk(self):
        removeLVM(self.private_img)
        if self.vm.is_updateable():
            removeLVM(self.root_img)
        shutil.rmtree(self.vmdir)

    def clone_disk_files(self, src_vm, verbose):
        if verbose:
            self.log.info("--> Creating directory: {0}".format(self.vmdir))
        os.mkdir (self.vmdir)

        if src_vm.private_img is not None and self.private_img is not None:
            if verbose:
                print >> sys.stderr, "--> Snapshotting the private image:\n{0} ==>\n{1}".\
                        format(src_vm.private_img, self.private_img)
                snapshotLVM(src_vm.private_img, self.private_img)

        if src_vm.updateable and src_vm.root_img is not None and self.root_img is not None:
            if verbose:
                print >> sys.stderr, "--> Copying the root image:\n{0} ==>\n{1}".\
                        format(src_vm.root_img, self.root_img)
            if src_vm.storage_type == "file":
                self._copy_file(src_vm.root_img, self.root_img)
            else:
                snapshotLVM(src_vm.root_img, self.root_img)
            # TODO: modules?

        clean_volatile_img = src_vm.dir_path + "/clean-volatile.img.tar"
        if os.path.exists(clean_volatile_img):
            self._copy_file(clean_volatile_img, self.vm.dir_path + "/clean-volatile.img.tar")

    def commit_template_changes(self):
        pass

def removeLVM(img):
    retcode = subprocess.call (["sudo", "lvremove", "-f", img]) 
    log.debug("Removing LVM %s"  % img)
    if retcode != 0:
        log.info("No old root LVM to remove" % img)

def snapshotLVM(old, new_name):
    retcode = subprocess.call (["sudo", "lvcreate", "-s", old, "-n", new_name]) 
    if retcode != 0:
        raise IOError("Error snapshoting %s as %s" % (old, new_name))

    retcode = subprocess.call (["sudo", "lvchange", "-kn", "-ay", new_name]) 
    if retcode != 0:
        raise IOError("Error snapshoting %s as %s" % (old, new_name))
    return new_name


def createEmptyImg(name, size):
    log.debug("Creating new Thin LVM %s in %s VG %s bytes"  % (name, VG, size))
    retcode = subprocess.call (["sudo", "lvcreate", "-T", "%s/pool00" % VG, '-n', name, '-V', str(size)+"B"]) 
    if retcode != 0:
        raise IOError ("Error creating thin LVM %s" % name)
    retcode = subprocess.call(["sudo", "lvchange", "-kn", "-ay", name])
    if retcode != 0:
        raise IOError ("Error activation LVM %s" % name)
    retcode = subprocess.call (["sudo", "mkfs.ext4", name])
    if retcode != 0:
        raise IOError ("Error making ext4 fs")
    return name



def renameLVM(old_name, new_name):
    log.debug("Renaming LVM  %s to %s " % (old_name, new_name))
    retcode = subprocess.call (["sudo", "lvrename", "%s/%s" % (VG,
                os.path.basename(old_name)), os.path.basename(new_name)]) 
    if retcode != 0:
        raise IOError ("Error renaming LVM  %s to %s " % (old_name, new_name) )
    return new_name

