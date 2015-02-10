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

from qubes.storage.xen import QubesXenVmStorage

VG = 'qubes_dom0'
LVM = '/dev/' + VG + '/'

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class QubesLvmVmStorage(QubesXenVmStorage):

    def __init__(self, vm, **kwargs):
        super(QubesLvmVmStorage, self).__init__(vm, **kwargs)
        self.private_img = LVM + vm.name + "-private"

    def _get_privatedev(self):
        return "'phy:%s,%s,w'," % (self.private_img, self.private_dev)

    def create_on_disk_private_img(self, verbose, source_template = None):
        self.log.debug("Creating empty private img for %s" % self.vm.name)



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
        shutil.rmtree(self.vmdir)


def removeLVM(img):
    retcode = subprocess.call (["sudo", "lvremove", "-f", img]) 
    log.debug("Removing LVM %s"  % img)
    if retcode != 0:
        raise IOError ("Error removing LVM %s" % img)

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

