#
# This is the SPEC file for creating binary RPMs for the Dom0.
#
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2010  Rafal Wojtczuk  <rafal@invisiblethingslab.com>
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

#%{!?python3_sitelib: %define python3_sitelib %(%{__python3} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(False)")}

%{!?version: %define version %(cat version)}

# debug_package hack should be removed when BuildArch:noarch is enabled below
%define debug_package %{nil}

%define _dracutmoddir	/usr/lib/dracut/modules.d
%if %{fedora} < 17
%define _dracutmoddir   /usr/share/dracut/modules.d
%endif

Name:		qubes-core-dom0
Version:	%{version}
Release:	1%{dist}
Summary:	The Qubes core files (Dom0-side)

Group:		Qubes
Vendor:		Invisible Things Lab
License:	GPL
URL:		http://www.qubes-os.org

# because we have "#!/usr/bin/env python" shebangs, RPM puts
# "Requires: $(which # python)" dependency, which, depending on $PATH order,
# may point to /usr/bin/python or /bin/python (because Fedora has this stupid
# /bin -> usr/bin symlink). python*.rpm provides only /usr/bin/python.
AutoReq:	no

# FIXME: Enable this and disable debug_package
#BuildArch: noarch

BuildRequires:  ImageMagick
BuildRequires:	systemd-units

BuildRequires:  python3-devel

# for building documentation
BuildRequires:	python3-sphinx
BuildRequires:	libvirt-python3
BuildRequires:	python3-dbus

Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
Requires:	python, pciutils, python-inotify, python-daemon
Requires:	python-setuptools
Requires:       qubes-core-dom0-linux >= 3.1.8
Requires:       qubes-core-dom0-doc
Requires:       qubes-db-dom0
Requires:       python3-lxml
# TODO: R: qubes-gui-dom0 >= 2.1.11
Conflicts:      qubes-gui-dom0 < 1.1.13
Requires:       libvirt-python3
%if x%{?backend_vmm} == xxen
Requires:       xen-runtime
Requires:       xen-hvm
Requires:       libvirt-daemon-xen >= 1.2.20-6
%endif
Requires:       createrepo
Requires:       gnome-packagekit
Requires:       cronie
Requires:       bsdtar
Requires:       python3-jinja2
# for qubes-hcl-report
Requires:       dmidecode
Requires:       PyQt4

# for property's docstrings
Requires:	python3-docutils

# for lvm support
Requires: lvm2-python-libs

# Prevent preupgrade from installation (it pretend to provide distribution upgrade)
Obsoletes:	preupgrade < 2.0
Provides:	preupgrade = 2.0
%define _builddir %(pwd)

%description
The Qubes core files for installation on Dom0.

%prep
# we operate on the current directory, so no need to unpack anything
# symlink is to generate useful debuginfo packages
rm -f %{name}-%{version}
ln -sf . %{name}-%{version}
%setup -T -D

%build

make all

%install

make install \
    DESTDIR=$RPM_BUILD_ROOT \
    UNITDIR=%{_unitdir} \
    PYTHON_SITEPATH=%{python3_sitelib} \
    SYSCONFDIR=%{_sysconfdir}

%post

# Create NetworkManager configuration if we do not have it
if ! [ -e /etc/NetworkManager/NetworkManager.conf ]; then
echo '[main]' > /etc/NetworkManager/NetworkManager.conf
echo 'plugins = keyfile' >> /etc/NetworkManager/NetworkManager.conf
echo '[keyfile]' >> /etc/NetworkManager/NetworkManager.conf
fi

sed '/^autoballoon=/d;/^lockfile=/d' -i /etc/xen/xl.conf
echo 'autoballoon=0' >> /etc/xen/xl.conf
echo 'lockfile="/var/run/qubes/xl-lock"' >> /etc/xen/xl.conf

if [ -e /etc/sysconfig/prelink ]; then
sed 's/^PRELINKING\s*=.*/PRELINKING=no/' -i /etc/sysconfig/prelink
fi

systemctl --no-reload enable qubes-core.service >/dev/null 2>&1
systemctl --no-reload enable qubes-netvm.service >/dev/null 2>&1
systemctl --no-reload enable qubes-setupdvm.service >/dev/null 2>&1

# Conflicts with libxl stack, so disable it
systemctl --no-reload disable xend.service >/dev/null 2>&1
systemctl --no-reload disable xendomains.service >/dev/null 2>&1
systemctl daemon-reload >/dev/null 2>&1 || :

HAD_SYSCONFIG_NETWORK=yes
if ! [ -e /etc/sysconfig/network ]; then
    HAD_SYSCONFIG_NETWORK=no
    # supplant empty one so NetworkManager init script does not complain
    touch /etc/sysconfig/network
fi

# Load evtchn module - xenstored needs it
modprobe evtchn 2> /dev/null || modprobe xen-evtchn
service xenstored start

if ! [ -e /var/lib/qubes/qubes.xml ]; then
#    echo "Initializing Qubes DB..."
    umask 007; sg qubes -c 'qubes-create --offline-mode'
    qubes-prefs --force-root --offline-mode default-kernel `ls /var/lib/qubes/vm-kernels|head -n 1` 2> /dev/null
fi

# Because we now have an installer
# this script is always executed during upgrade
# and we decided not to restart core during upgrade
#service qubes_core start

if [ "x"$HAD_SYSCONFIG_NETWORK = "xno" ]; then
    rm -f /etc/sysconfig/network
fi

%clean
rm -rf $RPM_BUILD_ROOT
rm -f %{name}-%{version}

%pre
if ! grep -q ^qubes: /etc/group ; then
		groupadd qubes
fi

%triggerin -- xen-runtime
/usr/lib/qubes/fix-dir-perms.sh

%preun
if [ "$1" = 0 ] ; then
	# no more packages left
    service qubes_netvm stop
    service qubes_core stop
fi

%postun
if [ "$1" = 0 ] ; then
	# no more packages left
    chgrp root /etc/xen
    chmod 700 /etc/xen
    groupdel qubes
fi

%files
%defattr(-,root,root,-)
%config(noreplace) %attr(0664,root,qubes) %{_sysconfdir}/qubes/qmemman.conf
/usr/bin/qvm-*
/usr/bin/qubes-*
/usr/bin/qmemmand

%dir %{python3_sitelib}/qubes-*.egg-info
%{python3_sitelib}/qubes-*.egg-info/*

%dir %{python3_sitelib}/qubes
%dir %{python3_sitelib}/qubes/__pycache__
%{python3_sitelib}/qubes/__pycache__/*
%{python3_sitelib}/qubes/__init__.py
%{python3_sitelib}/qubes/app.py
%{python3_sitelib}/qubes/backup.py
%{python3_sitelib}/qubes/config.py
%{python3_sitelib}/qubes/core2migration.py
%{python3_sitelib}/qubes/devices.py
%{python3_sitelib}/qubes/dochelpers.py
%{python3_sitelib}/qubes/events.py
%{python3_sitelib}/qubes/firewall.py
%{python3_sitelib}/qubes/exc.py
%{python3_sitelib}/qubes/log.py
%{python3_sitelib}/qubes/rngdoc.py
%{python3_sitelib}/qubes/tarwriter.py
%{python3_sitelib}/qubes/utils.py

%dir %{python3_sitelib}/qubes/vm
%dir %{python3_sitelib}/qubes/vm/__pycache__
%{python3_sitelib}/qubes/vm/__pycache__/*
%{python3_sitelib}/qubes/vm/__init__.py
%{python3_sitelib}/qubes/vm/adminvm.py
%{python3_sitelib}/qubes/vm/appvm.py
%{python3_sitelib}/qubes/vm/dispvm.py
%{python3_sitelib}/qubes/vm/qubesvm.py
%{python3_sitelib}/qubes/vm/standalonevm.py
%{python3_sitelib}/qubes/vm/templatevm.py

%dir %{python3_sitelib}/qubes/vm/mix
%dir %{python3_sitelib}/qubes/vm/mix/__pycache__
%{python3_sitelib}/qubes/vm/mix/__pycache__/*
%{python3_sitelib}/qubes/vm/mix/__init__.py
%{python3_sitelib}/qubes/vm/mix/net.py

%dir %{python3_sitelib}/qubes/storage
%dir %{python3_sitelib}/qubes/storage/__pycache__
%{python3_sitelib}/qubes/storage/__pycache__/*
%{python3_sitelib}/qubes/storage/__init__.py
%{python3_sitelib}/qubes/storage/file.py
%{python3_sitelib}/qubes/storage/domain.py
%{python3_sitelib}/qubes/storage/kernels.py
%{python3_sitelib}/qubes/storage/lvm.py

%dir %{python3_sitelib}/qubes/tools
%dir %{python3_sitelib}/qubes/tools/__pycache__
%{python3_sitelib}/qubes/tools/__pycache__/*
%{python3_sitelib}/qubes/tools/__init__.py
%{python3_sitelib}/qubes/tools/qmemmand.py
%{python3_sitelib}/qubes/tools/qubes_create.py
%{python3_sitelib}/qubes/tools/qubes_monitor_layout_notify.py
%{python3_sitelib}/qubes/tools/qubes_prefs.py
%{python3_sitelib}/qubes/tools/qvm_block.py
%{python3_sitelib}/qubes/tools/qvm_backup.py
%{python3_sitelib}/qubes/tools/qvm_backup_restore.py
%{python3_sitelib}/qubes/tools/qvm_create.py
%{python3_sitelib}/qubes/tools/qvm_device.py
%{python3_sitelib}/qubes/tools/qvm_features.py
%{python3_sitelib}/qubes/tools/qvm_firewall.py
%{python3_sitelib}/qubes/tools/qvm_check.py
%{python3_sitelib}/qubes/tools/qvm_clone.py
%{python3_sitelib}/qubes/tools/qvm_kill.py
%{python3_sitelib}/qubes/tools/qvm_ls.py
%{python3_sitelib}/qubes/tools/qvm_pause.py
%{python3_sitelib}/qubes/tools/qvm_pool.py
%{python3_sitelib}/qubes/tools/qvm_prefs.py
%{python3_sitelib}/qubes/tools/qvm_remove.py
%{python3_sitelib}/qubes/tools/qvm_run.py
%{python3_sitelib}/qubes/tools/qvm_shutdown.py
%{python3_sitelib}/qubes/tools/qvm_start.py
%{python3_sitelib}/qubes/tools/qvm_tags.py
%{python3_sitelib}/qubes/tools/qvm_template_commit.py
%{python3_sitelib}/qubes/tools/qvm_template_postprocess.py
%{python3_sitelib}/qubes/tools/qvm_unpause.py

%dir %{python3_sitelib}/qubes/ext
%dir %{python3_sitelib}/qubes/ext/__pycache__
%{python3_sitelib}/qubes/ext/__pycache__/*
%{python3_sitelib}/qubes/ext/__init__.py
%{python3_sitelib}/qubes/ext/gui.py
%{python3_sitelib}/qubes/ext/pci.py
%{python3_sitelib}/qubes/ext/qubesmanager.py
%{python3_sitelib}/qubes/ext/r3compatibility.py

%dir %{python3_sitelib}/qubes/tests
%dir %{python3_sitelib}/qubes/tests/__pycache__
%{python3_sitelib}/qubes/tests/__pycache__/*
%{python3_sitelib}/qubes/tests/__init__.py
%{python3_sitelib}/qubes/tests/run.py
%{python3_sitelib}/qubes/tests/extra.py

%{python3_sitelib}/qubes/tests/app.py
%{python3_sitelib}/qubes/tests/devices.py
%{python3_sitelib}/qubes/tests/events.py
%{python3_sitelib}/qubes/tests/firewall.py
%{python3_sitelib}/qubes/tests/init.py
%{python3_sitelib}/qubes/tests/storage.py
%{python3_sitelib}/qubes/tests/storage_file.py
%{python3_sitelib}/qubes/tests/storage_lvm.py
%{python3_sitelib}/qubes/tests/tarwriter.py

%dir %{python3_sitelib}/qubes/tests/vm
%dir %{python3_sitelib}/qubes/tests/vm/__pycache__
%{python3_sitelib}/qubes/tests/vm/__pycache__/*
%{python3_sitelib}/qubes/tests/vm/__init__.py
%{python3_sitelib}/qubes/tests/vm/init.py
%{python3_sitelib}/qubes/tests/vm/adminvm.py
%{python3_sitelib}/qubes/tests/vm/qubesvm.py

%dir %{python3_sitelib}/qubes/tests/vm/mix
%dir %{python3_sitelib}/qubes/tests/vm/mix/__pycache__
%{python3_sitelib}/qubes/tests/vm/mix/__pycache__/*
%{python3_sitelib}/qubes/tests/vm/mix/__init__.py
%{python3_sitelib}/qubes/tests/vm/mix/net.py

%dir %{python3_sitelib}/qubes/tests/tools
%dir %{python3_sitelib}/qubes/tests/tools/__pycache__
%{python3_sitelib}/qubes/tests/tools/__pycache__/*
%{python3_sitelib}/qubes/tests/tools/__init__.py
%{python3_sitelib}/qubes/tests/tools/init.py
%{python3_sitelib}/qubes/tests/tools/qvm_device.py
%{python3_sitelib}/qubes/tests/tools/qvm_firewall.py
%{python3_sitelib}/qubes/tests/tools/qvm_ls.py

%dir %{python3_sitelib}/qubes/tests/integ
%dir %{python3_sitelib}/qubes/tests/integ/__pycache__
%{python3_sitelib}/qubes/tests/integ/__pycache__/*
%{python3_sitelib}/qubes/tests/integ/__init__.py
%{python3_sitelib}/qubes/tests/integ/backup.py
%{python3_sitelib}/qubes/tests/integ/backupcompatibility.py
%{python3_sitelib}/qubes/tests/integ/basic.py
%{python3_sitelib}/qubes/tests/integ/devices_pci.py
%{python3_sitelib}/qubes/tests/integ/dispvm.py
%{python3_sitelib}/qubes/tests/integ/dom0_update.py
%{python3_sitelib}/qubes/tests/integ/network.py
%{python3_sitelib}/qubes/tests/integ/storage.py
%{python3_sitelib}/qubes/tests/integ/vm_qrexec_gui.py

%dir %{python3_sitelib}/qubes/tests/integ/tools
%dir %{python3_sitelib}/qubes/tests/integ/tools/__pycache__
%{python3_sitelib}/qubes/tests/integ/tools/__pycache__/*
%{python3_sitelib}/qubes/tests/integ/tools/__init__.py
%{python3_sitelib}/qubes/tests/integ/tools/qubes_create.py
%{python3_sitelib}/qubes/tests/integ/tools/qvm_firewall.py
%{python3_sitelib}/qubes/tests/integ/tools/qvm_check.py
%{python3_sitelib}/qubes/tests/integ/tools/qvm_prefs.py
%{python3_sitelib}/qubes/tests/integ/tools/qvm_run.py

%dir %{python3_sitelib}/qubes/qmemman
%dir %{python3_sitelib}/qubes/qmemman/__pycache__
%{python3_sitelib}/qubes/qmemman/__pycache__/*
%{python3_sitelib}/qubes/qmemman/__init__.py
%{python3_sitelib}/qubes/qmemman/algo.py
%{python3_sitelib}/qubes/qmemman/client.py

/usr/lib/qubes/unbind-pci-device.sh
/usr/lib/qubes/cleanup-dispvms
/usr/lib/qubes/qfile-daemon-dvm*
/usr/lib/qubes/block-cleaner-daemon.py*
/usr/lib/qubes/vusb-ctl.py*
/usr/lib/qubes/xl-qvm-usb-attach.py*
/usr/lib/qubes/xl-qvm-usb-detach.py*
/usr/lib/qubes/fix-dir-perms.sh
/usr/lib/qubes/startup-dvm.sh
/usr/lib/qubes/startup-misc.sh
/usr/lib/qubes/prepare-volatile-img.sh
/usr/libexec/qubes/qubes-notify-tools
/usr/libexec/qubes/qubes-notify-updates
%{_unitdir}/qubes-block-cleaner.service
%{_unitdir}/qubes-core.service
%{_unitdir}/qubes-setupdvm.service
%{_unitdir}/qubes-netvm.service
%{_unitdir}/qubes-qmemman.service
%{_unitdir}/qubes-vm@.service
%{_unitdir}/qubes-reload-firewall@.service
%{_unitdir}/qubes-reload-firewall@.timer
%attr(2770,root,qubes) %dir /var/lib/qubes
%attr(2770,root,qubes) %dir /var/lib/qubes/vm-templates
%attr(2770,root,qubes) %dir /var/lib/qubes/appvms
%attr(2770,root,qubes) %dir /var/lib/qubes/servicevms
%attr(2770,root,qubes) %dir /var/lib/qubes/backup
%attr(2770,root,qubes) %dir /var/lib/qubes/dvmdata
%attr(2770,root,qubes) %dir /var/lib/qubes/vm-kernels
/usr/share/qubes/templates/libvirt/xen.xml
/usr/share/qubes/templates/libvirt/devices/pci.xml
/usr/share/qubes/templates/libvirt/devices/net.xml
/usr/lib/tmpfiles.d/qubes.conf
/usr/lib/qubes/qubes-prepare-saved-domain.sh
/usr/lib/qubes/qubes-update-dispvm-savefile-with-progress.sh
/etc/xen/scripts/block.qubes
/etc/xen/scripts/block-snapshot
/etc/xen/scripts/block-origin
/etc/xen/scripts/vif-route-qubes
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.FeaturesRequest
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.Filecopy
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.GetImageRGBA
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.GetRandomizedTime
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.NotifyTools
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.NotifyUpdates
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.OpenInVM
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.OpenURL
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.VMShell
/etc/qubes-rpc/qubes.FeaturesRequest
/etc/qubes-rpc/qubes.GetRandomizedTime
/etc/qubes-rpc/qubes.NotifyTools
/etc/qubes-rpc/qubes.NotifyUpdates
%attr(2770,root,qubes) %dir /var/log/qubes
%attr(0770,root,qubes) %dir /var/run/qubes
/etc/xdg/autostart/qubes-guid.desktop

/usr/share/doc/qubes/relaxng/*.rng
