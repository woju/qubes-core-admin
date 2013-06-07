#!/usr/bin/python2
# -*- coding: utf-8 -*-
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
import sys
import libvirt
import time
from qubes.qubes import QubesVm,QubesVmLabel,register_qubes_vm_class
from qubes.qubes import QubesDispVmLabels
from qubes.qubes import dry_run,vmm
from qubes.qmemman_client import QMemmanClient

class QubesDisposableVm(QubesVm):
    """
    A class that represents an DisposableVM. A child of QubesVm.
    """

    # In which order load this VM type from qubes.xml
    load_order = 120

    def get_attrs_config(self):
        attrs_config = super(QubesDisposableVm, self).get_attrs_config()

        attrs_config['name']['eval'] = '"disp%d" % self._qid if value is None else value'

        # New attributes
        attrs_config['dispid'] = { 'func': lambda x: self._qid if x is None else int(x),
            'save': lambda: str(self.dispid) }
        attrs_config['include_in_backups']['func'] = lambda x: False
        attrs_config['disp_savefile'] = {
                'default': '/var/run/qubes/current-savefile',
                'save': lambda: str(self.disp_savefile) }

        return attrs_config

    def __init__(self, **kwargs):

        disp_template = None
        if 'disp_template' in kwargs.keys():
            disp_template = kwargs['disp_template']
            kwargs['template'] = disp_template.template
            kwargs['dir_path'] = disp_template.dir_path
        super(QubesDisposableVm, self).__init__(**kwargs)

        assert self.template is not None, "Missing template for DisposableVM!"

        if disp_template:
            self.clone_attrs(disp_template)

        # Use DispVM icon with the same color
        if self._label:
            self._label = QubesDispVmLabels[self._label.name]
            self.icon_path = self._label.icon_path

    @property
    def type(self):
        return "DisposableVM"

    def is_disposablevm(self):
        return True

    @property
    def ip(self):
        if self.netvm is not None:
            return self.netvm.get_ip_for_dispvm(self.dispid)
        else:
            return None

    def get_clone_attrs(self):
        attrs = super(QubesDisposableVm, self).get_clone_attrs()
        attrs.remove('_label')
        return attrs

    def do_not_use_get_xml_attrs(self):
        # Minimal set - do not inherit rest of attributes
        attrs = {}
        attrs["qid"] = str(self.qid)
        attrs["name"] = self.name
        attrs["dispid"] = str(self.dispid)
        attrs["template_qid"] = str(self.template.qid)
        attrs["label"] = self.label.name
        attrs["firewall_conf"] = self.relative_path(self.firewall_conf)
        attrs["netvm_qid"] = str(self.netvm.qid) if self.netvm is not None else "none"
        return attrs

    def verify_files(self):
        return True

    def create_xenstore_entries(self, xid):
        super(QubesDisposableVm, self).create_xenstore_entries(xid)

        # TODO!
        domain_path = vmm.xs.get_domain_path(xid)

        vmm.xs.write('', "{0}/qubes-restore-complete".format(domain_path),
                'True')

    def get_config_params(self):
        attrs = super(QubesDisposableVm, self).get_config_params()
        attrs['privatedev'] = ''
        return attrs

    def start(self, verbose = False, **kwargs):
        if dry_run:
            return

        # Intentionally not used is_running(): eliminate also "Paused", "Crashed", "Halting"
        if self.get_power_state() != "Halted":
            raise QubesException ("VM is already running!")

        # skip netvm state checking - calling VM have the same netvm, so it
        # must be already running

        if verbose:
            print >> sys.stderr, "--> Loading the VM (type = {0})...".format(self.type)

        print >>sys.stderr, "time=%s, creating config file" % (str(time.time()))
        # refresh config file
        domain_config = self.create_config_file()

        mem_required = int(self.memory) * 1024 * 1024
        print >>sys.stderr, "time=%s, getting %d memory" % (str(time.time()), mem_required)
        qmemman_client = QMemmanClient()
        try:
            got_memory = qmemman_client.request_memory(mem_required)
        except IOError as e:
            raise IOError("ERROR: Failed to connect to qmemman: %s" % str(e))
        if not got_memory:
            qmemman_client.close()
            raise MemoryError ("ERROR: insufficient memory to start VM '%s'" % self.name)

        # dispvm cannot have PCI devices
        assert (len(self.pcidevs) == 0), "DispVM cannot have PCI devices"

        print >>sys.stderr, "time=%s, calling restore" % (str(time.time()))
        vmm.libvirt_conn.restoreFlags(self.disp_savefile,
                domain_config, libvirt.VIR_DOMAIN_SAVE_PAUSED)

        print >>sys.stderr, "time=%s, done" % (str(time.time()))
        self._libvirt_domain = None

        self.services['qubes-dvm'] = True
        if verbose:
            print >> sys.stderr, "--> Setting Xen Store info for the VM..."
        self.create_xenstore_entries(self.xid)
        print >>sys.stderr, "time=%s, done xenstore" % (str(time.time()))

        # fire hooks
        for hook in self.hooks_start:
            hook(self, verbose = verbose, **kwargs)

        if verbose:
            print >> sys.stderr, "--> Starting the VM..."
        self.libvirt_domain.resume()
        print >>sys.stderr, "time=%s, resumed" % (str(time.time()))

# close() is not really needed, because the descriptor is close-on-exec
# anyway, the reason to postpone close() is that possibly xl is not done
# constructing the domain after its main process exits
# so we close() when we know the domain is up
# the successful unpause is some indicator of it
        qmemman_client.close()

        if self._start_guid_first and kwargs.get('start_guid', True) and os.path.exists('/var/run/shm.id'):
            self.start_guid(verbose=verbose,
                    notify_function=kwargs.get('notify_function', None))

        self.start_qrexec_daemon(verbose=verbose,
                notify_function=kwargs.get('notify_function', None))
        print >>sys.stderr, "time=%s, qrexec done" % (str(time.time()))

        if not self._start_guid_first and kwargs.get('start_guid', True) and os.path.exists('/var/run/shm.id'):
            self.start_guid(verbose=verbose,
                    notify_function=kwargs.get('notify_function', None))
        print >>sys.stderr, "time=%s, guid done" % (str(time.time()))

        return self.xid

# register classes
register_qubes_vm_class(QubesDisposableVm)
