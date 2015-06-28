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

import datetime
import fcntl
import lxml.etree
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.parsers.expat
import xen.lowlevel.xc
from qubes import qmemman
from qubes import qmemman_algo
from qubes.storage.xen import QubesXenVmStorage
from qubes.storage.lvm import QubesLvmVmStorage, LVM

from qubes.qubes import xs,dry_run,xc,xl_ctx
from qubes.qubes import register_qubes_vm_class
from qubes.qubes import QubesVmCollection,QubesException,QubesHost,QubesVmLabels
from qubes.qubes import defaults,system_path,vm_files,qubes_max_qid
from qubes.qmemman_client import QMemmanClient

import qubes.qubesutils

xid_to_name_cache = {}

class QubesVm(object):
    """
    A representation of one Qubes VM
    Only persistent information are stored here, while all the runtime
    information, e.g. Xen dom id, etc, are to be retrieved via Xen API
    Note that qid is not the same as Xen's domid!
    """

    # In which order load this VM type from qubes.xml
    load_order = 100

    # hooks for plugins (modules) which want to influence existing classes,
    # without introducing new ones
    hooks_clone_disk_files = []
    hooks_create_on_disk = []
    hooks_create_xenstore_entries = []
    hooks_get_attrs_config = []
    hooks_get_clone_attrs = []
    hooks_get_config_params = []
    hooks_init = []
    hooks_label_setter = []
    hooks_netvm_setter = []
    hooks_post_rename = []
    hooks_pre_rename = []
    hooks_remove_from_disk = []
    hooks_start = []
    hooks_verify_files = []
    hooks_set_attr = []

    def get_attrs_config(self):
        """ Object attributes for serialization/deserialization
            inner dict keys:
             - order: initialization order (to keep dependency intact)
                      attrs without order will be evaluated at the end
             - default: default value used when attr not given to object constructor
             - attr: set value to this attribute instead of parameter name
             - eval: (DEPRECATED) assign result of this expression instead of
                      value directly; local variable 'value' contains
                      attribute value (or default if it was not given)
             - func: callable used to parse the value retrieved from XML
             - save: use evaluation result as value for XML serialization; only attrs with 'save' key will be saved in XML
             - save_skip: if present and evaluates to true, attr will be omitted in XML
             - save_attr: save to this XML attribute instead of parameter name
             """

        attrs = {
            # __qid cannot be accessed by setattr, so must be set manually in __init__
            "qid": { "attr": "_qid", "order": 0 },
            "name": { "order": 1 },
            "dir_path": { "default": None, "order": 2 },
            "storage_type": {"default": "file", "order":4, "attr":"_storage_type"},
            "conf_file": {
                "func": lambda value: self.absolute_path(value, self.name +
                                                                 ".conf"),
                "order": 3 },
            ### order >= 10: have base attrs set
            "firewall_conf": {
                "func": self._absolute_path_gen(vm_files["firewall_conf"]),
                "order": 10 },
            "installed_by_rpm": { "default": False, 'order': 10 },
            "template": { "default": None, "attr": '_template', 'order': 10 },
            ### order >= 20: have template set
            "uses_default_netvm": { "default": True, 'order': 20 },
            "netvm": { "default": None, "attr": "_netvm", 'order': 20 },
            "label": { "attr": "_label", "default": defaults["appvm_label"], 'order': 20,
                'xml_deserialize': lambda _x: QubesVmLabels[_x] },
            "memory": { "default": defaults["memory"], 'order': 20 },
            "maxmem": { "default": None, 'order': 25 },
            "pcidevs": {
                "default": '[]',
                "order": 25,
                "func": lambda value: [] if value in ["none", None]  else
                    eval(value) if value.find("[") >= 0 else
                    eval("[" + value + "]") },
            # Internal VM (not shown in qubes-manager, doesn't create appmenus entries
            "internal": { "default": False, 'attr': '_internal' },
            "vcpus": { "default": None },
            "uses_default_kernel": { "default": True, 'order': 30 },
            "uses_default_kernelopts": { "default": True, 'order': 30 },
            "kernel": {
                "attr": "_kernel",
                "default": None,
                "order": 31,
                "func": lambda value: self._collection.get_default_kernel() if
                  self.uses_default_kernel else value },
            "kernelopts": {
                "default": "",
                "order": 31,
                "func": lambda value: value if not self.uses_default_kernelopts\
                    else defaults["kernelopts_pcidevs"] if len(self.pcidevs)>0 \
                    else defaults["kernelopts"] },
            "mac": { "attr": "_mac", "default": None },
            "include_in_backups": {
                "func": lambda x: x if x is not None
                else not self.installed_by_rpm },
            "services": {
                "default": {},
                "func": lambda value: eval(str(value)) },
            "debug": { "default": False },
            "default_user": { "default": "user", "attr": "_default_user" },
            "qrexec_timeout": { "default": 60 },
            "autostart": { "default": False, "attr": "_autostart" },
            "backup_content" : { 'default': False },
            "backup_size" : {
                "default": 0,
                "func": int },
            "backup_path" : { 'default': "" },
            "backup_timestamp": {
                "func": lambda value:
                    datetime.datetime.fromtimestamp(int(value)) if value
                    else None },
            ##### Internal attributes - will be overriden in __init__ regardless of args
            "config_file_template": {
                "func": lambda x: system_path["config_template_pv"] },
            "icon_path": {
                "func": lambda x: os.path.join(self.dir_path, "icon.png") if
                               self.dir_path is not None else None },
            # used to suppress side effects of clone_attrs
            "_do_not_reset_firewall": { "func": lambda x: False },
            "kernels_dir": {
                # for backward compatibility (or another rare case): kernel=None -> kernel in VM dir
                "func": lambda x: \
                    os.path.join(system_path["qubes_kernels_base_dir"],
                                 self.kernel) if self.kernel is not None \
                        else os.path.join(self.dir_path,
                                          vm_files["kernels_subdir"]) },
            "_start_guid_first": { "func": lambda x: False },
            }

        ### Mark attrs for XML inclusion
        # Simple string attrs
        for prop in ['qid', 'name', 'dir_path', 'storage_type', 'memory', 'maxmem', 'pcidevs',
        'vcpus', 'internal', 'uses_default_kernel', 'kernel',
        'uses_default_kernelopts', 'kernelopts', 'services', 'installed_by_rpm',
        'uses_default_netvm', 'include_in_backups', 'debug',
        'qrexec_timeout', 'autostart', 'backup_content', 'backup_size',
        'backup_path' ]:
            attrs[prop]['save'] = lambda prop=prop: str(getattr(self, prop))
        # Simple paths
        for prop in ['conf_file']:
            attrs[prop]['save'] = \
                lambda prop=prop: self.relative_path(getattr(self, prop))
            attrs[prop]['save_skip'] = \
                lambda prop=prop: getattr(self, prop) is None

        attrs['mac']['save'] = lambda: str(self._mac)
        attrs['mac']['save_skip'] = lambda: self._mac is None

        attrs['default_user']['save'] = lambda: str(self._default_user)

        attrs['backup_timestamp']['save'] = \
            lambda: self.backup_timestamp.strftime("%s")
        attrs['backup_timestamp']['save_skip'] = \
            lambda: self.backup_timestamp is None

        attrs['netvm']['save'] = \
            lambda: str(self.netvm.qid) if self.netvm is not None else "none"
        attrs['netvm']['save_attr'] = "netvm_qid"
        attrs['template']['save'] = \
            lambda: str(self.template.qid) if self.template else "none"
        attrs['template']['save_attr'] = "template_qid"
        attrs['label']['save'] = lambda: self.label.name

        # fire hooks
        for hook in self.hooks_get_attrs_config:
            attrs = hook(self, attrs)
        return attrs

    def post_set_attr(self, attr, newvalue, oldvalue):
        for hook in self.hooks_set_attr:
            hook(self, attr, newvalue, oldvalue)

    def __basic_parse_xml_attr(self, value):
        if value is None:
            return None
        if value.lower() == "none":
            return None
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if value.isdigit():
            return int(value)
        return value

    def __init__(self, **kwargs):

        self._collection = None
        if 'collection' in kwargs:
            self._collection = kwargs['collection']
        else:
            raise ValueError("No collection given to QubesVM constructor")

        # Special case for template b/c it is given in "template_qid" property
        if "xml_element" in kwargs and kwargs["xml_element"].get("template_qid"):
            template_qid = kwargs["xml_element"].get("template_qid")
            if template_qid.lower() != "none":
                if int(template_qid) in self._collection:
                    kwargs["template"] = self._collection[int(template_qid)]
                else:
                    raise ValueError("Unknown template with QID %s" % template_qid)
        attrs = self.get_attrs_config()
        for attr_name in sorted(attrs, key=lambda _x: attrs[_x]['order'] if 'order' in attrs[_x] else 1000):
            attr_config = attrs[attr_name]
            attr = attr_name
            if 'attr' in attr_config:
                attr = attr_config['attr']
            value = None
            if attr_name in kwargs:
                value = kwargs[attr_name]
            elif 'xml_element' in kwargs and kwargs['xml_element'].get(attr_name) is not None:
                if 'xml_deserialize' in attr_config and callable(attr_config['xml_deserialize']):
                    value = attr_config['xml_deserialize'](kwargs['xml_element'].get(attr_name))
                else:
                    value = self.__basic_parse_xml_attr(kwargs['xml_element'].get(attr_name))
            else:
                if 'default' in attr_config:
                    value = attr_config['default']
            if 'func' in attr_config:
                setattr(self, attr, attr_config['func'](value))
            elif 'eval' in attr_config:
                setattr(self, attr, eval(attr_config['eval']))
            else:
               setattr(self, attr, value)

        #Init private attrs
        self.__qid = self._qid

        assert self.__qid < qubes_max_qid, "VM id out of bounds!"
        assert self.name is not None

        if not self.verify_name(self.name):
            msg = ("'%s' is invalid VM name (invalid characters, over 31 chars long, "
                   "or one of 'none', 'true', 'false')") % self.name
            if 'xml_element' in kwargs:
                print >>sys.stderr, "WARNING: %s" % msg
            else:
                raise QubesException(msg)

        if self.netvm is not None:
            self.netvm.connected_vms[self.qid] = self

        # Not in generic way to not create QubesHost() to frequently
        if self.maxmem is None:
            qubes_host = QubesHost()
            total_mem_mb = qubes_host.memory_total/1024
            self.maxmem = total_mem_mb/2
        
        # Linux specific cap: max memory can't scale beyond 10.79*init_mem
        if self.maxmem > self.memory * 10:
            self.maxmem = self.memory * 10

        # By default allow use all VCPUs
        if self.vcpus is None:
            qubes_host = QubesHost()
            self.vcpus = qubes_host.no_cpus

        # Always set if meminfo-writer should be active or not
        if 'meminfo-writer' not in self.services:
            self.services['meminfo-writer'] = not (len(self.pcidevs) > 0)

        # Additionally force meminfo-writer disabled when VM have PCI devices
        if len(self.pcidevs) > 0:
            self.services['meminfo-writer'] = False

        # Initialize VM image storage class
        self.storage = self._getStorage()
        if hasattr(self, 'kernels_dir'):
            self.storage.modules_img = os.path.join(self.kernels_dir,
                    "modules.img")
            self.storage.modules_img_rw = self.kernel is None

        # Some additional checks for template based VM
        if self.template is not None:
            if not self.template.is_template():
                print >> sys.stderr, "ERROR: template_qid={0} doesn't point to a valid TemplateVM".\
                    format(self.template.qid)
                return
            self.template.appvms[self.qid] = self
        else:
            assert self.root_img is not None, "Missing root_img for standalone VM!"

        self.xid = -1
        self.xid = self.get_xid()

        # fire hooks
        for hook in self.hooks_init:
            hook(self)

    def __repr__(self):
        return '<{} at {:#0x} qid={!r} name={!r}>'.format(
            self.__class__.__name__,
            id(self),
            self.qid,
            self.name)

    def absolute_path(self, arg, default):
        if arg is not None and os.path.isabs(arg):
            return arg
        else:
            return os.path.join(self.dir_path, (arg if arg is not None else default))

    def _absolute_path_gen(self, default):
        return lambda value: self.absolute_path(value, default)

    def relative_path(self, arg):
        return arg.replace(self.dir_path + '/', '')

    @property
    def qid(self):
        return self.__qid

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, new_label):
        self._label = new_label
        if self.icon_path:
            try:
                os.remove(self.icon_path)
            except:
                pass
            os.symlink (new_label.icon_path, self.icon_path)
            subprocess.call(['sudo', 'xdg-icon-resource', 'forceupdate'])

        # fire hooks
        for hook in self.hooks_label_setter:
            hook(self, new_label)

    @property
    def netvm(self):
        return self._netvm

    @property
    def storage_type(self):
        return self._storage_type

    def set_storage_type(self, type):
        self._storage_type = type

    # Don't know how properly call setter from base class, so workaround it...
    @netvm.setter
    def netvm(self, new_netvm):
        self._set_netvm(new_netvm)
        # fire hooks
        for hook in self.hooks_netvm_setter:
            hook(self, new_netvm)

    def _set_netvm(self, new_netvm):
        if self.is_running() and new_netvm is not None and not new_netvm.is_running():
            raise QubesException("Cannot dynamically attach to stopped NetVM")
        if self.netvm is not None:
            self.netvm.connected_vms.pop(self.qid)
            if self.is_running():
                subprocess.call(["xl", "network-detach", self.name, "0"], stderr=subprocess.PIPE)
                if hasattr(self.netvm, 'post_vm_net_detach'):
                    self.netvm.post_vm_net_detach(self)

        if new_netvm is None:
            if not self._do_not_reset_firewall:
                # Set also firewall to block all traffic as discussed in #370
                if os.path.exists(self.firewall_conf):
                    shutil.copy(self.firewall_conf, os.path.join(system_path["qubes_base_dir"],
                                "backup", "%s-firewall-%s.xml" % (self.name,
                                time.strftime('%Y-%m-%d-%H:%M:%S'))))
                self.write_firewall_conf({'allow': False, 'allowDns': False,
                        'allowIcmp': False, 'allowYumProxy': False, 'rules': []})
        else:
            new_netvm.connected_vms[self.qid]=self

        self._netvm = new_netvm

        if new_netvm is None:
            return

        if self.is_running():
            # refresh IP, DNS etc
            self.create_xenstore_entries()
            self.attach_network()
            if hasattr(self.netvm, 'post_vm_net_attach'):
                self.netvm.post_vm_net_attach(self)

    @property
    def ip(self):
        if self.netvm is not None:
            return self.netvm.get_ip_for_vm(self.qid)
        else:
            return None

    @property
    def netmask(self):
        if self.netvm is not None:
            return self.netvm.netmask
        else:
            return None

    @property
    def gateway(self):
        # This is gateway IP for _other_ VMs, so make sense only in NetVMs
        return None

    @property
    def secondary_dns(self):
        if self.netvm is not None:
            return self.netvm.secondary_dns
        else:
            return None

    @property
    def vif(self):
        if self.xid < 0:
            return None
        if self.netvm is None:
            return None
        return "vif{0}.+".format(self.xid)

    @property
    def mac(self):
        if self._mac is not None:
            return self._mac
        else:
            return "00:16:3E:5E:6C:{qid:02X}".format(qid=self.qid)

    @mac.setter
    def mac(self, new_mac):
        self._mac = new_mac

    @property
    def kernel(self):
        return self._kernel

    @kernel.setter
    def kernel(self, new_value):
        if new_value is not None:
            if not os.path.exists(os.path.join(system_path[
                'qubes_kernels_base_dir'], new_value)):
                raise QubesException("Kernel '%s' not installed" % new_value)
            for f in ('vmlinuz', 'modules.img'):
                if not os.path.exists(os.path.join(
                        system_path['qubes_kernels_base_dir'], new_value, f)):
                    raise QubesException(
                        "Kernel '%s' not properly installed: missing %s "
                        "file" % (new_value, f))
        self._kernel = new_value

    @property
    def updateable(self):
        return self.template is None

    # Leaved for compatibility
    def is_updateable(self):
        return self.updateable

    @property
    def default_user(self):
        if self.template is not None:
            return self.template.default_user
        else:
            return self._default_user

    @default_user.setter
    def default_user(self, value):
        self._default_user = value

    def is_networked(self):
        if self.is_netvm():
            return True

        if self.netvm is not None:
            return True
        else:
            return False

    def verify_name(self, name):
        if not isinstance(self.__basic_parse_xml_attr(name), str):
            return False
        if len(name) > 31:
            return False
        return re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name) is not None

    def pre_rename(self, new_name):
        # fire hooks
        for hook in self.hooks_pre_rename:
            hook(self, new_name)

    def set_name(self, name):
        if self.is_running():
            raise QubesException("Cannot change name of running VM!")

        if not self.verify_name(name):
            raise QubesException("Invalid characters in VM name")

        if self.installed_by_rpm:
            raise QubesException("Cannot rename VM installed by RPM -- first clone VM and then use yum to remove package.")

        self.pre_rename(name)

        new_conf = os.path.join(self.dir_path, name + '.conf')
        if os.path.exists(self.conf_file):
            os.rename(self.conf_file, new_conf)
        old_dirpath = self.dir_path
        old_name = self.name
        self.storage.rename(self.name, name)
        self.name = name
        new_dirpath = self.storage.vmdir
        if self.conf_file is not None:
            self.conf_file = new_conf.replace(old_dirpath, new_dirpath)
        if self.icon_path is not None:
            self.icon_path = self.icon_path.replace(old_dirpath, new_dirpath)
        if hasattr(self, 'kernels_dir') and self.kernels_dir is not None:
            self.kernels_dir = self.kernels_dir.replace(old_dirpath, new_dirpath)
        self.dir_path = new_dirpath

        self.post_rename(old_name)

    def post_rename(self, old_name):
        # fire hooks
        for hook in self.hooks_post_rename:
            hook(self, old_name)

    @property
    def internal(self):
        return self._internal

    @internal.setter
    def internal(self, value):
        oldvalue = self._internal
        self._internal = value
        self.post_set_attr('internal', value, oldvalue)

    @property
    def autostart(self):
        return self._autostart

    @autostart.setter
    def autostart(self, value):
        if value:
            retcode = subprocess.call(["sudo", "ln", "-sf",
                                       "/usr/lib/systemd/system/qubes-vm@.service",
                                       "/etc/systemd/system/multi-user.target.wants/qubes-vm@%s.service" % self.name])
        else:
            retcode = subprocess.call(["sudo", "systemctl", "disable", "qubes-vm@%s.service" % self.name])
        if retcode != 0:
            raise QubesException("Failed to set autostart for VM via systemctl")
        self._autostart = bool(value)

    @classmethod
    def is_template_compatible(cls, template):
        """Check if given VM can be a template for this VM"""
        # FIXME: check if the value is instance of QubesTemplateVM, not the VM
        # type. The problem is while this file is loaded, QubesTemplateVM is
        # not defined yet.
        if template and (not template.is_template() or template.type != "TemplateVM"):
            return False
        return True

    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, value):
        if self._template is None and value is not None:
            raise QubesException("Cannot set template for standalone VM")
        if value and not self.is_template_compatible(value):
            raise QubesException("Incompatible template type %s with VM of type %s" % (value.type, self.type))
        self._template = value

    def is_template(self):
        return False

    def is_appvm(self):
        return False

    def is_netvm(self):
        return False

    def is_proxyvm(self):
        return False

    def is_disposablevm(self):
        return False

    def _xid_to_name(self, xid):
        if xid in xid_to_name_cache:
            return xid_to_name_cache[xid]
        else:
            domname = xl_ctx.domid_to_name(xid)
            if domname:
                xid_to_name_cache[xid] = domname
            return domname

    def get_xl_dominfo(self):
        if dry_run:
            return

        start_xid = self.xid

        domains = xl_ctx.list_domains()
        for dominfo in domains:
            if dominfo.domid == start_xid:
                return dominfo
            elif dominfo.domid < start_xid:
                # the current XID can't lower than one noticed earlier, if VM
                # was restarted in the meantime, the next XID will greater
                continue
            domname = self._xid_to_name(dominfo.domid)
            if domname == self.name:
                self.xid = dominfo.domid
                return dominfo
        return None

    def get_xc_dominfo(self, name = None):
        if dry_run:
            return

        if name is None:
            name = self.name

        start_xid = self.xid
        if start_xid < 0:
            start_xid = 0
        try:
            domains = xc.domain_getinfo(start_xid, qubes_max_qid)
        except xen.lowlevel.xc.Error:
            return None

        # If previous XID is still valid, this is the right domain - XID can't
        # be reused for another domain until system reboot
        if start_xid > 0 and domains[0]['domid'] == start_xid:
            return domains[0]

        for dominfo in domains:
            domname = self._xid_to_name(dominfo['domid'])
            if domname == name:
                return dominfo
        return None

    def get_xid(self):
        if dry_run:
            return 666

        dominfo = self.get_xc_dominfo()
        if dominfo:
            self.xid = dominfo['domid']
            return self.xid
        else:
            return -1

    def get_uuid(self):

        dominfo = self.get_xl_dominfo()
        if dominfo:
            vmuuid = uuid.UUID(''.join('%02x' % b for b in dominfo.uuid))
            return vmuuid
        else:
            return None

    def get_mem(self):
        if dry_run:
            return 666

        dominfo = self.get_xc_dominfo()
        if dominfo:
            return dominfo['mem_kb']
        else:
            return 0

    def get_mem_static_max(self):
        if dry_run:
            return 666

        dominfo = self.get_xc_dominfo()
        if dominfo:
            return dominfo['maxmem_kb']
        else:
            return 0

    def get_prefmem(self):
        untrusted_meminfo_key = xs.read('', '/local/domain/%s/memory/meminfo'
                                            % self.xid)
        if untrusted_meminfo_key is None or untrusted_meminfo_key == '':
            return 0
        domain = qmemman.DomainState(self.xid)
        qmemman_algo.refresh_meminfo_for_domain(domain, untrusted_meminfo_key)
        domain.memory_maximum = self.get_mem_static_max()*1024
        return qmemman_algo.prefmem(domain)/1024

    def get_per_cpu_time(self):
        if dry_run:
            import random
            return random.random() * 100

        dominfo = self.get_xc_dominfo()
        if dominfo:
            return dominfo['cpu_time']/dominfo['online_vcpus']
        else:
            return 0

    def get_disk_utilization_root_img(self):
        return qubes.qubesutils.get_disk_usage(self.root_img)

    def get_root_img_sz(self):
        if not os.path.exists(self.root_img):
            return 0

        return os.path.getsize(self.root_img)

    def get_power_state(self):
        if dry_run:
            return "NA"

        dominfo = self.get_xc_dominfo()
        if dominfo:
            if dominfo['paused']:
                return "Paused"
            elif dominfo['crashed']:
                return "Crashed"
            elif dominfo['shutdown']:
                if dominfo['shutdown_reason'] == 2:
                    return "Suspended"
                else:
                    return "Halting"
            elif dominfo['dying']:
                return "Dying"
            else:
                if not self.is_fully_usable():
                    return "Transient"
                else:
                    return "Running"
        else:
            return 'Halted'

        return "NA"

    def is_guid_running(self):
        xid = self.get_xid()
        if xid < 0:
            return False
        if not os.path.exists('/var/run/qubes/guid-running.%d' % xid):
            return False
        return True

    def is_qrexec_running(self):
        if self.xid < 0:
            return False
        return os.path.exists('/var/run/qubes/qrexec.%s' % self.name)

    def is_fully_usable(self):
        # Running gui-daemon implies also VM running
        if not self.is_guid_running():
            return False
        if not self.is_qrexec_running():
            return False
        return True

    def is_running(self):
        # in terms of Xen and internal logic - starting VM is running
        if self.get_power_state() in ["Running", "Transient", "Halting"]:
            return True
        else:
            return False

    def is_paused(self):
        if self.get_power_state() == "Paused":
            return True
        else:
            return False

    def get_start_time(self):
        if not self.is_running():
            return None

        dominfo = self.get_xl_dominfo()

        uuid = self.get_uuid()

        start_time = xs.read('', "/vm/%s/start_time" % str(uuid))
        if start_time != '':
            return datetime.datetime.fromtimestamp(float(start_time))
        else:
            return None

    def is_outdated(self):
        return self.storage.is_outdated()

    @property
    def private_img(self):
        return self.storage.private_img

    @property
    def root_img(self):
        return self.storage.root_img

    @property
    def volatile_img(self):
        return self.storage.volatile_img

    def get_disk_utilization(self):
        return qubes.qubesutils.get_disk_usage(self.dir_path)

    def get_disk_utilization_private_img(self):
        return qubes.qubesutils.get_disk_usage(self.private_img)

    def get_private_img_sz(self):
        self.storage.get_private_img_sz()

    def resize_private_img(self, size):
        self.storage.resize_private_img(size)
        if self.is_running():
            retcode = self.run("while [ \"`blockdev --getsize64 /dev/xvdb`\" -lt {0} ]; do ".format(size) +
                "head /dev/xvdb > /dev/null; sleep 0.2; done; resize2fs /dev/xvdb", user="root", wait=True)
        if retcode != 0:
            raise QubesException("resize2fs failed")



    # FIXME: should be outside of QubesVM?
    def get_timezone(self):
        # fc18
        if os.path.islink('/etc/localtime'):
            return '/'.join(os.readlink('/etc/localtime').split('/')[-2:])
        # <=fc17
        elif os.path.exists('/etc/sysconfig/clock'):
            clock_config = open('/etc/sysconfig/clock', "r")
            clock_config_lines = clock_config.readlines()
            clock_config.close()
            zone_re = re.compile(r'^ZONE="(.*)"')
            for line in clock_config_lines:
                line_match = zone_re.match(line)
                if line_match:
                    return line_match.group(1)
        else:
            # last resort way, some applications makes /etc/localtime
            # hardlink instead of symlink...
            tz_info = os.stat('/etc/localtime')
            if not tz_info:
                return None
            if tz_info.st_nlink > 1:
                p = subprocess.Popen(['find', '/usr/share/zoneinfo',
                                       '-inum', str(tz_info.st_ino)],
                                      stdout=subprocess.PIPE)
                tz_path = p.communicate()[0].strip()
                return tz_path.replace('/usr/share/zoneinfo/', '')
        return None

    def cleanup_vifs(self):
        """
        Xend does not remove vif when backend domain is down, so we must do it
        manually
        """

        if not self.is_running():
            return

        dev_basepath = '/local/domain/%d/device/vif' % self.xid
        for dev in xs.ls('', dev_basepath):
            # check if backend domain is alive
            backend_xid = int(xs.read('', '%s/%s/backend-id' % (dev_basepath, dev)))
            if xl_ctx.domid_to_name(backend_xid) is not None:
                # check if device is still active
                if xs.read('', '%s/%s/state' % (dev_basepath, dev)) == '4':
                    continue
            # remove dead device
            xs.rm('', '%s/%s' % (dev_basepath, dev))

    def create_xenstore_entries(self, xid = None):
        if dry_run:
            return

        if xid is None:
            xid = self.xid

        domain_path = xs.get_domain_path(xid)

        # Set Xen Store entires with VM networking info:

        xs.write('', "{0}/qubes-vm-type".format(domain_path),
                self.type)
        xs.write('', "{0}/qubes-vm-updateable".format(domain_path),
                str(self.updateable))

        if self.is_netvm():
            xs.write('',
                    "{0}/qubes-netvm-gateway".format(domain_path),
                    self.gateway)
            xs.write('',
                    "{0}/qubes-netvm-secondary-dns".format(domain_path),
                    self.secondary_dns)
            xs.write('',
                    "{0}/qubes-netvm-netmask".format(domain_path),
                    self.netmask)
            xs.write('',
                    "{0}/qubes-netvm-network".format(domain_path),
                    self.network)

        if self.netvm is not None:
            xs.write('', "{0}/qubes-ip".format(domain_path), self.ip)
            xs.write('', "{0}/qubes-netmask".format(domain_path),
                    self.netvm.netmask)
            xs.write('', "{0}/qubes-gateway".format(domain_path),
                    self.netvm.gateway)
            xs.write('',
                    "{0}/qubes-secondary-dns".format(domain_path),
                    self.netvm.secondary_dns)

        tzname = self.get_timezone()
        if tzname:
             xs.write('',
                     "{0}/qubes-timezone".format(domain_path),
                     tzname)

        for srv in self.services.keys():
            # convert True/False to "1"/"0"
            xs.write('', "{0}/qubes-service/{1}".format(domain_path, srv),
                    str(int(self.services[srv])))

        xs.write('',
                "{0}/qubes-block-devices".format(domain_path),
                '')

        xs.write('',
                "{0}/qubes-usb-devices".format(domain_path),
                '')

        xs.write('', "{0}/qubes-debug-mode".format(domain_path),
                str(int(self.debug)))

        # Fix permissions
        xs.set_permissions('', '{0}/device'.format(domain_path),
                [{ 'dom': xid }])
        xs.set_permissions('', '{0}/memory'.format(domain_path),
                [{ 'dom': xid }])
        xs.set_permissions('', '{0}/qubes-block-devices'.format(domain_path),
                [{ 'dom': xid }])
        xs.set_permissions('', '{0}/qubes-usb-devices'.format(domain_path),
                [{ 'dom': xid }])

        # fire hooks
        for hook in self.hooks_create_xenstore_entries:
            hook(self, xid=xid)

    def get_config_params(self, source_template=None):
        args = {}
        args['name'] = self.name
        if hasattr(self, 'kernels_dir'):
            args['kerneldir'] = self.kernels_dir
        args['vmdir'] = self.dir_path
        args['pcidev'] = str(self.pcidevs).strip('[]')
        args['mem'] = str(self.memory)
        if self.maxmem < self.memory:
            args['mem'] = str(self.maxmem)
        args['maxmem'] = str(self.maxmem)
        if 'meminfo-writer' in self.services and not self.services['meminfo-writer']:
            # If dynamic memory management disabled, set maxmem=mem
            args['maxmem'] = args['mem']
        args['vcpus'] = str(self.vcpus)
        if self.netvm is not None:
            args['ip'] = self.ip
            args['mac'] = self.mac
            args['gateway'] = self.netvm.gateway
            args['dns1'] = self.netvm.gateway
            args['dns2'] = self.secondary_dns
            args['netmask'] = self.netmask
            args['netdev'] = "'mac={mac},script=/etc/xen/scripts/vif-route-qubes,ip={ip}".format(ip=self.ip, mac=self.mac)
            if self.netvm.qid != 0:
                args['netdev'] += ",backend={0}".format(self.netvm.name)
            args['netdev'] += "'"
            args['disable_network'] = '';
        else:
            args['ip'] = ''
            args['mac'] = ''
            args['gateway'] = ''
            args['dns1'] = ''
            args['dns2'] = ''
            args['netmask'] = ''
            args['netdev'] = ''
            args['disable_network'] = '#';
        args.update(self.storage.get_config_params())
        if hasattr(self, 'kernelopts'):
            args['kernelopts'] = self.kernelopts
            if self.debug:
                print >> sys.stderr, "--> Debug mode: adding 'earlyprintk=xen' to kernel opts"
                args['kernelopts'] += ' earlyprintk=xen'

        # fire hooks
        for hook in self.hooks_get_config_params:
            args = hook(self, args)

        return args

    @property
    def uses_custom_config(self):
        return self.conf_file != self.absolute_path(self.name + ".conf", None)

    def create_config_file(self, file_path = None, source_template = None, prepare_dvm = False):
        if file_path is None:
            file_path = self.conf_file
            if self.uses_custom_config:
                return
        if source_template is None:
            source_template = self.template

        f_conf_template = open(self.config_file_template, 'r')
        conf_template = f_conf_template.read()
        f_conf_template.close()

        template_params = self.get_config_params(source_template)
        if prepare_dvm:
            template_params['name'] = '%NAME%'
            template_params['privatedev'] = ''
            template_params['netdev'] = re.sub(r"ip=[0-9.]*", "ip=%IP%", template_params['netdev'])
        if os.path.exists(file_path):
            os.unlink(file_path)
        conf_appvm = open(file_path, "w")

        conf_appvm.write(conf_template.format(**template_params))
        conf_appvm.close()

    def create_on_disk(self, verbose=False, source_template = None):
        if source_template is None:
            source_template = self.template
        assert source_template is not None
        self.set_storage_type(source_template.storage_type)
        self.storage = self._getStorage()
        if dry_run:
            return

        self.storage.create_on_disk(verbose, source_template)
        if self.updateable:
            kernels_dir = source_template.kernels_dir
            if verbose:
                print >> sys.stderr, "--> Copying the kernel (set kernel \"none\" to use it): {0}".\
                        format(kernels_dir)

            os.mkdir (self.dir_path + '/kernels')
            for f in ("vmlinuz", "initramfs", "modules.img"):
                shutil.copy(os.path.join(kernels_dir, f),
                        os.path.join(self.dir_path, vm_files["kernels_subdir"], f))

        if verbose:
            print >> sys.stderr, "--> Creating icon symlink: {0} -> {1}".format(self.icon_path, self.label.icon_path)
        os.symlink (self.label.icon_path, self.icon_path)

        # fire hooks
        for hook in self.hooks_create_on_disk:
            hook(self, verbose, source_template=source_template)

    def get_clone_attrs(self):
        attrs = ['kernel', 'uses_default_kernel', 'netvm', 'uses_default_netvm', 'storage_type',\
            'memory', 'maxmem', 'kernelopts', 'uses_default_kernelopts', 'services', 'vcpus', \
            '_mac', 'pcidevs', 'include_in_backups', '_label', 'default_user']

        # fire hooks
        for hook in self.hooks_get_clone_attrs:
            attrs = hook(self, attrs)

        return attrs

    def clone_attrs(self, src_vm, fail_on_error=True):
        self._do_not_reset_firewall = True
        for prop in self.get_clone_attrs():
            try:
                if prop == "storage_type":
                    self.set_storage_type(getattr(src_vm, prop))
                    self.storage = self._getStorage()
                else:
                    setattr(self, prop, getattr(src_vm, prop))
            except Exception as e:
                if fail_on_error:
                    self._do_not_reset_firewall = False
                    raise
                else:
                    print >>sys.stderr, "WARNING: %s" % str(e)
        self._do_not_reset_firewall = False

    def clone_disk_files(self, src_vm, verbose):
        if dry_run:
            return

        if src_vm.is_running():
            raise QubesException("Attempt to clone a running VM!")

        self.storage.clone_disk_files(src_vm, verbose)

        if src_vm.icon_path is not None and self.icon_path is not None:
            if os.path.exists (src_vm.dir_path):
                if os.path.islink(src_vm.icon_path):
                    icon_path = os.readlink(src_vm.icon_path)
                    if verbose:
                        print >> sys.stderr, "--> Creating icon symlink: {0} -> {1}".format(self.icon_path, icon_path)
                    os.symlink (icon_path, self.icon_path)
                else:
                    if verbose:
                        print >> sys.stderr, "--> Copying icon: {0} -> {1}".format(src_vm.icon_path, self.icon_path)
                    shutil.copy(src_vm.icon_path, self.icon_path)

        # fire hooks
        for hook in self.hooks_clone_disk_files:
            hook(self, src_vm, verbose)

    def verify_files(self):
        if dry_run:
            return

	self.storage.verify_files()
        # fire hooks
        for hook in self.hooks_verify_files:
            hook(self)

        return True


    def remove_from_disk(self):
        if dry_run:
            return

        # fire hooks
        for hook in self.hooks_remove_from_disk:
            hook(self)

        self.storage.remove_from_disk()

    def write_firewall_conf(self, conf):
        defaults = self.get_firewall_conf()
        expiring_rules_present = False
        for item in defaults.keys():
            if item not in conf:
                conf[item] = defaults[item]

        root = lxml.etree.Element(
                "QubesFirewallRules",
                policy = "allow" if conf["allow"] else "deny",
                dns = "allow" if conf["allowDns"] else "deny",
                icmp = "allow" if conf["allowIcmp"] else "deny",
                yumProxy = "allow" if conf["allowYumProxy"] else "deny"
        )

        for rule in conf["rules"]:
            # For backward compatibility
            if "proto" not in rule:
                if rule["portBegin"] is not None and rule["portBegin"] > 0:
                    rule["proto"] = "tcp"
                else:
                    rule["proto"] = "any"
            element = lxml.etree.Element(
                    "rule",
                    address=rule["address"],
                    proto=str(rule["proto"]),
            )
            if rule["netmask"] is not None and rule["netmask"] != 32:
                element.set("netmask", str(rule["netmask"]))
            if rule.get("portBegin", None) is not None and \
                            rule["portBegin"] > 0:
                element.set("port", str(rule["portBegin"]))
            if rule.get("portEnd", None) is not None and rule["portEnd"] > 0:
                element.set("toport", str(rule["portEnd"]))
            if "expire" in rule:
                element.set("expire", str(rule["expire"]))
                expiring_rules_present = True

            root.append(element)

        tree = lxml.etree.ElementTree(root)

        try:
            f = open(self.firewall_conf, 'a') # create the file if not exist
            f.close()

            with open(self.firewall_conf, 'w') as f:
                fcntl.lockf(f, fcntl.LOCK_EX)
                tree.write(f, encoding="UTF-8", pretty_print=True)
                fcntl.lockf(f, fcntl.LOCK_UN)
            f.close()
        except EnvironmentError as err:
            print >> sys.stderr, "{0}: save error: {1}".format(
                    os.path.basename(sys.argv[0]), err)
            return False

        # Automatically enable/disable 'yum-proxy-setup' service based on allowYumProxy
        if conf['allowYumProxy']:
            self.services['yum-proxy-setup'] = True
        else:
            if self.services.has_key('yum-proxy-setup'):
                self.services.pop('yum-proxy-setup')

        if expiring_rules_present:
            subprocess.call(["sudo", "systemctl", "start",
                             "qubes-reload-firewall@%s.timer" % self.name])

        return True

    def has_firewall(self):
        return os.path.exists (self.firewall_conf)

    def get_firewall_defaults(self):
        return { "rules": list(), "allow": True, "allowDns": True, "allowIcmp": True, "allowYumProxy": False }

    def get_firewall_conf(self):
        conf = self.get_firewall_defaults()

        try:
            tree = lxml.etree.parse(self.firewall_conf)
            root = tree.getroot()

            conf["allow"] = (root.get("policy") == "allow")
            conf["allowDns"] = (root.get("dns") == "allow")
            conf["allowIcmp"] = (root.get("icmp") == "allow")
            conf["allowYumProxy"] = (root.get("yumProxy") == "allow")

            for element in root:
                rule = {}
                attr_list = ("address", "netmask", "proto", "port", "toport",
                             "expire")

                for attribute in attr_list:
                    rule[attribute] = element.get(attribute)

                if rule["netmask"] is not None:
                    rule["netmask"] = int(rule["netmask"])
                else:
                    rule["netmask"] = 32

                if rule["port"] is not None:
                    rule["portBegin"] = int(rule["port"])
                else:
                    # backward compatibility
                    rule["portBegin"] = 0

                # For backward compatibility
                if rule["proto"] is None:
                    if rule["portBegin"] > 0:
                        rule["proto"] = "tcp"
                    else:
                        rule["proto"] = "any"

                if rule["toport"] is not None:
                    rule["portEnd"] = int(rule["toport"])
                else:
                    rule["portEnd"] = None

                if rule["expire"] is not None:
                    rule["expire"] = int(rule["expire"])
                    if rule["expire"] <= int(datetime.datetime.now().strftime(
                            "%s")):
                        continue
                else:
                    del(rule["expire"])

                del(rule["port"])
                del(rule["toport"])

                conf["rules"].append(rule)

        except EnvironmentError as err:
            return conf
        except (xml.parsers.expat.ExpatError,
                ValueError, LookupError) as err:
            print("{0}: load error: {1}".format(
                os.path.basename(sys.argv[0]), err))
            return None

        return conf

    def pci_add(self, pci):
        if not os.path.exists('/sys/bus/pci/devices/0000:%s' % pci):
            raise QubesException("Invalid PCI device: %s" % pci)
        if self.pcidevs.count(pci):
            # already added
            return
        self.pcidevs.append(pci)
        if self.is_running():
            try:
                subprocess.check_call(['sudo', system_path["qubes_pciback_cmd"], pci])
                subprocess.check_call(['sudo', 'xl', 'pci-attach', str(self.xid), pci])
            except Exception as e:
                print >>sys.stderr, "Failed to attach PCI device on the fly " \
                    "(%s), changes will be seen after VM restart" % str(e)

    def pci_remove(self, pci):
        if not self.pcidevs.count(pci):
            # not attached
            return
        self.pcidevs.remove(pci)
        if self.is_running():
            p = subprocess.Popen(['xl', 'pci-list', str(self.xid)],
                    stdout=subprocess.PIPE)
            result = p.communicate()
            m = re.search(r"^(\d+.\d+)\s+0000:%s$" % pci, result[0], flags=re.MULTILINE)
            if not m:
                print >>sys.stderr, "Device %s already detached" % pci
                return
            vmdev = m.group(1)
            try:
                self.run_service("qubes.DetachPciDevice",
                                 user="root", input="00:%s" % vmdev)
                subprocess.check_call(['sudo', 'xl', 'pci-detach', str(self.xid), pci])
            except Exception as e:
                print >>sys.stderr, "Failed to detach PCI device on the fly " \
                    "(%s), changes will be seen after VM restart" % str(e)

    def run(self, command, user = None, verbose = True, autostart = False,
            notify_function = None,
            passio = False, passio_popen = False, passio_stderr=False,
            ignore_stderr=False, localcmd = None, wait = False, gui = True,
            filter_esc = False):
        """command should be in form 'cmdline'
            When passio_popen=True, popen object with stdout connected to pipe.
            When additionally passio_stderr=True, stderr also is connected to pipe.
            When ignore_stderr=True, stderr is connected to /dev/null.
            """

        if user is None:
            user = self.default_user
        null = None
        if not self.is_running() and not self.is_paused():
            if not autostart:
                raise QubesException("VM not running")

            try:
                if notify_function is not None:
                    notify_function ("info", "Starting the '{0}' VM...".format(self.name))
                elif verbose:
                    print >> sys.stderr, "Starting the VM '{0}'...".format(self.name)
                xid = self.start(verbose=verbose, start_guid = gui, notify_function=notify_function)
            except (IOError, OSError, QubesException) as err:
                raise QubesException("Error while starting the '{0}' VM: {1}".format(self.name, err))
            except (MemoryError) as err:
                raise QubesException("Not enough memory to start '{0}' VM! "
                                     "Close one or more running VMs and try "
                                     "again.".format(self.name))

        if self.is_paused():
            raise QubesException("VM is paused")
        if not self.is_qrexec_running():
            raise QubesException(
                "Domain '{}': qrexec not connected.".format(self.name))

        xid = self.get_xid()
        if gui and os.getenv("DISPLAY") is not None and not self.is_guid_running():
            self.start_guid(verbose = verbose, notify_function = notify_function)

        args = [system_path["qrexec_client_path"], "-d", str(xid), "%s:%s" % (user, command)]
        if localcmd is not None:
            args += [ "-l", localcmd]
        if filter_esc:
            args += ["-t"]
        if os.isatty(sys.stderr.fileno()):
            args += ["-T"]

        call_kwargs = {}
        if ignore_stderr or not passio:
            null = open("/dev/null", "rw")
            call_kwargs['stderr'] = null
        if not passio:
            call_kwargs['stdin'] = null
            call_kwargs['stdout'] = null

        if passio_popen:
            popen_kwargs={'stdout': subprocess.PIPE}
            popen_kwargs['stdin'] = subprocess.PIPE
            if passio_stderr:
                popen_kwargs['stderr'] = subprocess.PIPE
            else:
                popen_kwargs['stderr'] = call_kwargs.get('stderr', None)
            p = subprocess.Popen (args, **popen_kwargs)
            if null:
                null.close()
            return p
        if not wait and not passio:
            args += ["-e"]
        retcode = subprocess.call(args, **call_kwargs)
        if null:
            null.close()
        return retcode

    def run_service(self, service, source="dom0", user=None,
                    passio_popen =  False, input=None):
        if input and passio_popen:
            raise ValueError("'input' and 'passio_popen' cannot be used "
                             "together")
        if input:
            return self.run("QUBESRPC %s %s" % (service, source),
                        localcmd="echo %s" % input, user=user, wait=True)
        else:
            return self.run("QUBESRPC %s %s" % (service, source),
                        passio_popen=passio_popen, user=user, wait=True)

    def attach_network(self, verbose = False, wait = True, netvm = None):
        if dry_run:
            return

        if not self.is_running():
            raise QubesException ("VM not running!")

        if netvm is None:
            netvm = self.netvm

        if netvm is None:
            raise QubesException ("NetVM not set!")

        if netvm.qid != 0:
            if not netvm.is_running():
                if verbose:
                    print >> sys.stderr, "--> Starting NetVM {0}...".format(netvm.name)
                netvm.start()

        xs_path = '/local/domain/%d/device/vif/0/state' % (self.xid)
        if xs.read('', xs_path) is not None:
            # TODO: check its state and backend state (this can be stale vif after NetVM restart)
            if verbose:
                print >> sys.stderr, "NOTICE: Network already attached"
                return

        xm_cmdline = ["/usr/sbin/xl", "network-attach", str(self.xid), "script=/etc/xen/scripts/vif-route-qubes", "ip="+self.ip, "backend="+netvm.name ]
        retcode = subprocess.call (xm_cmdline)
        if retcode != 0:
            print >> sys.stderr, ("WARNING: Cannot attach to network to '{0}'!".format(self.name))
        if wait:
            tries = 0
            while xs.read('', xs_path) != '4':
                tries += 1
                if tries > 50:
                    raise QubesException ("Network attach timed out!")
                time.sleep(0.2)

    def wait_for_session(self, notify_function = None):
        #self.run('echo $$ >> /tmp/qubes-session-waiter; [ ! -f /tmp/qubes-session-env ] && exec sleep 365d', ignore_stderr=True, gui=False, wait=True)

        # Note : User root is redefined to SYSTEM in the Windows agent code
        p = self.run('QUBESRPC qubes.WaitForSession none', user="root", passio_popen=True, gui=False, wait=True)
        p.communicate(input=self.default_user)

    def start_guid(self, verbose = True, notify_function = None,
            extra_guid_args=None, before_qrexec=False):
        if verbose:
            print >> sys.stderr, "--> Starting Qubes GUId..."
        xid = self.get_xid()

        guid_cmd = [system_path["qubes_guid_path"],
            "-d", str(xid),
            "-c", self.label.color,
            "-i", self.label.icon_path,
            "-l", str(self.label.index)]
        if extra_guid_args is not None:
            guid_cmd += extra_guid_args
        if self.debug:
            guid_cmd += ['-v', '-v']
        elif not verbose:
            guid_cmd += ['-q']
        retcode = subprocess.call (guid_cmd)
        if (retcode != 0) :
            raise QubesException("Cannot start qubes-guid!")

        if verbose:
            print >> sys.stderr, "--> Sending monitor layout..."

        try:
            subprocess.call([system_path["monitor_layout_notify_cmd"], self.name])
        except Exception as e:
            print >>sys.stderr, "ERROR: %s" % e

        if verbose:
            print >> sys.stderr, "--> Waiting for qubes-session..."

        self.wait_for_session(notify_function)

    def start_qrexec_daemon(self, verbose = False, notify_function = None):
        if verbose:
            print >> sys.stderr, "--> Starting the qrexec daemon..."
        xid = self.get_xid()
        qrexec_args = [str(xid), self.name, self.default_user]
        if not verbose:
            qrexec_args.insert(0, "-q")
        qrexec_env = os.environ
        qrexec_env['QREXEC_STARTUP_TIMEOUT'] = str(self.qrexec_timeout)
        retcode = subprocess.call ([system_path["qrexec_daemon_path"]] +
                                   qrexec_args, env=qrexec_env)
        if (retcode != 0) :
            raise OSError ("Cannot execute qrexec-daemon!")

    def start(self, debug_console = False, verbose = False,
              preparing_dvm =  False, start_guid = True, notify_function = None,
              mem_required = None):
        if dry_run:
            return

        # Intentionally not used is_running(): eliminate also "Paused", "Crashed", "Halting"
        if self.get_power_state() != "Halted":
            raise QubesException ("VM is already running!")

        self.verify_files()

        if self.netvm is not None:
            if self.netvm.qid != 0:
                if not self.netvm.is_running():
                    if verbose:
                        print >> sys.stderr, "--> Starting NetVM {0}...".format(self.netvm.name)
                    self.netvm.start(verbose = verbose, start_guid = start_guid, notify_function = notify_function)

        self.storage.prepare_for_vm_startup(verbose=verbose)
        if verbose:
            print >> sys.stderr, "--> Loading the VM (type = {0})...".format(self.type)

        # refresh config file
        self.create_config_file()

        if mem_required is None:
            mem_required = int(self.memory) * 1024 * 1024
        qmemman_client = QMemmanClient()
        try:
            got_memory = qmemman_client.request_memory(mem_required)
        except IOError as e:
            raise IOError("ERROR: Failed to connect to qmemman: %s" % str(e))
        if not got_memory:
            qmemman_client.close()
            raise MemoryError ("ERROR: insufficient memory to start VM '%s'" % self.name)

        # Bind pci devices to pciback driver
        for pci in self.pcidevs:
            try:
                subprocess.check_call(['sudo', system_path["qubes_pciback_cmd"], pci])
            except subprocess.CalledProcessError:
                raise QubesException("Failed to prepare PCI device %s" % pci)

        xl_cmdline = ['sudo', '/usr/sbin/xl', 'create', self.conf_file, '-q', '-p']

        try:
            subprocess.check_call(xl_cmdline)
        except:
            try:
                self._cleanup_zombie_domains()
            except:
                pass
            raise QubesException("Failed to load VM config")

        xid = self.get_xid()
        self.xid = xid

        if preparing_dvm:
            self.services['qubes-dvm'] = True
        if verbose:
            print >> sys.stderr, "--> Setting Xen Store info for the VM..."
        self.create_xenstore_entries(xid)

        if verbose:
            print >> sys.stderr, "--> Updating firewall rules..."
        netvm = self.netvm
        while netvm is not None:
            if netvm.is_proxyvm() and netvm.is_running():
                netvm.write_iptables_xenstore_entry()
            netvm = netvm.netvm

        # fire hooks
        for hook in self.hooks_start:
            hook(self, verbose = verbose, preparing_dvm =  preparing_dvm,
                    start_guid = start_guid, notify_function = notify_function)

        if verbose:
            print >> sys.stderr, "--> Starting the VM..."
        xc.domain_unpause(xid)

# close() is not really needed, because the descriptor is close-on-exec
# anyway, the reason to postpone close() is that possibly xl is not done
# constructing the domain after its main process exits
# so we close() when we know the domain is up
# the successful unpause is some indicator of it
        qmemman_client.close()

        if self._start_guid_first and start_guid and not preparing_dvm and os.path.exists('/var/run/shm.id'):
            self.start_guid(verbose=verbose, notify_function=notify_function, before_qrexec=True)

        if not preparing_dvm:
            self.start_qrexec_daemon(verbose=verbose,notify_function=notify_function)

        if start_guid and not preparing_dvm and os.path.exists('/var/run/shm.id'):
            self.start_guid(verbose=verbose, notify_function=notify_function)

        if preparing_dvm:
            if verbose:
                print >> sys.stderr, "--> Preparing config template for DispVM"
            self.create_config_file(file_path = self.dir_path + '/dvm.conf', prepare_dvm = True)

        return xid

    def _cleanup_zombie_domains(self):
        """
        This function is workaround broken libxl (which leaves not fully
        created domain on failure) and vchan on domain crash behaviour
        @return: None
        """
        xc = self.get_xc_dominfo()
        if xc and xc['dying'] == 1:
            # GUID still running?
            guid_pidfile = '/var/run/qubes/guid-running.%d' % xc['domid']
            if os.path.exists(guid_pidfile):
                guid_pid = open(guid_pidfile).read().strip()
                os.kill(int(guid_pid), 15)
            # qrexec still running?
            if self.is_qrexec_running():
                #TODO: kill qrexec daemon
                pass

    def shutdown(self, force=False, xid = None):
        if dry_run:
            return

        if not self.is_running():
            raise QubesException ("VM already stopped!")

        subprocess.call (['/usr/sbin/xl', 'shutdown', str(xid) if xid is not None else self.name])
        #xc.domain_destroy(self.get_xid())

    def force_shutdown(self, xid = None):
        if dry_run:
            return

        if not self.is_running() and not self.is_paused():
            raise QubesException ("VM already stopped!")

        subprocess.call(['sudo', '/usr/sbin/xl', 'destroy',
                         str(xid) if xid is not None else self.name])

    def suspend(self):
        if dry_run:
            return

        if not self.is_running() and not self.is_paused():
            raise QubesException ("VM already stopped!")

        if len (self.pcidevs) > 0:
            xs_path = '/local/domain/%d/control/shutdown' % self.get_xid()
            xs.write('', xs_path, 'suspend')
            tries = 0
            while self.get_power_state() != "Suspended":
                tries += 1
                if tries > 15:
                    # fallback to pause
                    print >>sys.stderr, "Failed to suspend domain %s, falling back to pause method" % self.name
                    self.pause()
                    break
                time.sleep(0.2)
        else:
            self.pause()

    def resume(self):
        if dry_run:
            return

        xc_info = self.get_xc_dominfo()
        if not xc_info:
            raise QubesException ("VM isn't started (cannot get xc_dominfo)!")

        if xc_info['shutdown_reason'] == 2:
            # suspended
            xc.domain_resume(xc_info['domid'], 1)
            xs.resume_domain(xc_info['domid'])
        else:
            self.unpause()

    def pause(self):
        if dry_run:
            return

        xc.domain_pause(self.get_xid())

    def unpause(self):
        if dry_run:
            return

        xc.domain_unpause(self.get_xid())

    def get_xml_attrs(self):
        attrs = {}
        attrs_config = self.get_attrs_config()
        for attr in attrs_config:
            attr_config = attrs_config[attr]
            if 'save' in attr_config:
                if 'save_skip' in attr_config:
                    if callable(attr_config['save_skip']):
                        if attr_config['save_skip']():
                            continue
                    elif eval(attr_config['save_skip']):
                        continue
                if callable(attr_config['save']):
                    value = attr_config['save']()
                else:
                    value = eval(attr_config['save'])
                if 'save_attr' in attr_config:
                    attrs[attr_config['save_attr']] = value
                else:
                    attrs[attr] = value
        return attrs

    def create_xml_element(self):
        # Compatibility hack (Qubes*VM in type vs Qubes*Vm in XML)...
        rx_type = re.compile (r"VM")

        attrs = self.get_xml_attrs()
        element = lxml.etree.Element(
            "Qubes" + rx_type.sub("Vm", self.type),
            **attrs)
        return element


    def _getStorage(self):
            if self.storage_type == 'lvm':
                return QubesLvmVmStorage(self)
            else:
                return QubesXenVmStorage(self)


register_qubes_vm_class(QubesVm)
