#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2014  Wojtek Porczyk <woju@invisiblethingslab.com>
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


qubes_base_dir   = "/var/lib/qubes"
system_path = {
    'qubes_guid_path': '/usr/bin/qubes-guid',
    'qrexec_daemon_path': '/usr/lib/qubes/qrexec-daemon',
    'qrexec_client_path': '/usr/lib/qubes/qrexec-client',
    'qubesdb_daemon_path': '/usr/sbin/qubesdb-daemon',

    'qubes_base_dir': qubes_base_dir,

    # Relative to qubes_base_dir
    'qubes_appvms_dir': 'appvms',
    'qubes_templates_dir': 'vm-templates',
    'qubes_servicevms_dir': 'servicevms',
    'qubes_store_filename': 'qubes.xml',
    'qubes_kernels_base_dir': 'vm-kernels',

    # qubes_icon_dir is obsolete
    # use QIcon.fromTheme() where applicable
    'qubes_icon_dir': '/usr/share/icons/hicolor/128x128/devices',

    'qrexec_policy_dir': '/etc/qubes-rpc/policy',

    'config_template_pv': '/usr/share/qubes/vm-template.xml',

    'qubes_pciback_cmd': '/usr/lib/qubes/unbind-pci-device.sh',
    'prepare_volatile_img_cmd': '/usr/lib/qubes/prepare-volatile-img.sh',
    'monitor_layout_notify_cmd': '/usr/bin/qubes-monitor-layout-notify',
}

vm_files = {
    'root_img': 'root.img',
    'rootcow_img': 'root-cow.img',
    'volatile_img': 'volatile.img',
    'clean_volatile_img': 'clean-volatile.img.tar',
    'private_img': 'private.img',
    'kernels_subdir': 'kernels',
    'firewall_conf': 'firewall.xml',
    'whitelisted_appmenus': 'whitelisted-appmenus.list',
    'updates_stat_file': 'updates.stat',
}

defaults = {
    'libvirt_uri': 'xen:///',
    'memory': 400,
    'kernelopts': "nopat",
    'kernelopts_pcidevs': "nopat iommu=soft swiotlb=4096",

    'dom0_update_check_interval': 6*3600,

    'private_img_size': 2*1024*1024*1024,
    'root_img_size': 10*1024*1024*1024,

    'storage_class': None,

    # how long (in sec) to wait for VMs to shutdown,
    # before killing them (when used qvm-run with --wait option),
    'shutdown_counter_max': 60,

    'vm_default_netmask': "255.255.255.0",

    # Set later
    'appvm_label': None,
    'template_label': None,
    'servicevm_label': None,
}

max_qid = 254
max_netid = 254
