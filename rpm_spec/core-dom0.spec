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
BuildRequires:  systemd

BuildRequires:  python3-devel

# for building documentation
BuildRequires:	python3-sphinx
BuildRequires:	python3-lxml
BuildRequires:	libvirt-python3
BuildRequires:	python3-dbus

Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units

Requires:       python3
#Requires:       python3-aiofiles
Requires:       python3-docutils
Requires:       python3-jinja2
Requires:       python3-lxml
Requires:       python3-pydbus
Requires:       python3-qubesdb
Requires:       python3-setuptools
Requires:       python3-xen
Requires:       libvirt-python3

Requires:       pciutils
Requires:       qubes-core-dom0-linux >= 3.1.8
Requires:       qubes-db-dom0
# TODO: R: qubes-gui-dom0 >= 2.1.11
Conflicts:      qubes-gui-dom0 < 1.1.13
%if x%{?backend_vmm} == xxen
Requires:       xen-runtime
Requires:       xen-hvm
Requires:       libvirt-daemon-xen >= 1.2.20-6
%endif
Requires:       createrepo
Requires:       gnome-packagekit
Requires:       cronie
Requires:       bsdtar
Requires:       scrypt
# for qubes-hcl-report
Requires:       dmidecode
Requires:       PyQt4

%{?systemd_requires}

# for lvm support
Requires: lvm2-python-libs

Obsoletes:	qubes-core-dom0-doc <= 4.0
Provides:	qubes-core-dom0-doc

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
make -C doc PYTHON=%{__python3} SPHINXBUILD=sphinx-build-%{python3_version} man

%install

make install \
    DESTDIR=$RPM_BUILD_ROOT \
    UNITDIR=%{_unitdir} \
    PYTHON_SITEPATH=%{python3_sitelib} \
    SYSCONFDIR=%{_sysconfdir}

make -C doc DESTDIR=$RPM_BUILD_ROOT \
    PYTHON=%{__python3} SPHINXBUILD=sphinx-build-%{python3_version} \
    install


%post
%systemd_post qubes-core.service
%systemd_post qubes-netvm.service
%systemd_post qubes-qmemman.service
%systemd_post qubesd.service

sed '/^autoballoon=/d;/^lockfile=/d' -i /etc/xen/xl.conf
echo 'autoballoon=0' >> /etc/xen/xl.conf
echo 'lockfile="/var/run/qubes/xl-lock"' >> /etc/xen/xl.conf

if [ -e /etc/sysconfig/prelink ]; then
sed 's/^PRELINKING\s*=.*/PRELINKING=no/' -i /etc/sysconfig/prelink
fi

# Conflicts with libxl stack, so disable it
systemctl --no-reload disable xend.service >/dev/null 2>&1
systemctl --no-reload disable xendomains.service >/dev/null 2>&1
systemctl daemon-reload >/dev/null 2>&1 || :

if ! [ -e /var/lib/qubes/qubes.xml ]; then
#    echo "Initializing Qubes DB..."
    umask 007; sg qubes -c 'qubes-create --offline-mode'
    qubes-prefs --force-root --offline-mode default-kernel `ls /var/lib/qubes/vm-kernels|head -n 1` 2> /dev/null
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
%systemd_preun qubes-core.service
%systemd_preun qubes-netvm.service
%systemd_preun qubes-qmemman.service
%systemd_preun qubesd.service

if [ "$1" = 0 ] ; then
	# no more packages left
    service qubes_netvm stop
    service qubes_core stop
fi

%postun
%systemd_postun qubes-core.service
%systemd_postun qubes-netvm.service
%systemd_postun_with_restart qubes-qmemman.service
%systemd_postun_with_restart qubesd.service

if [ "$1" = 0 ] ; then
	# no more packages left
    chgrp root /etc/xen
    chmod 700 /etc/xen
    groupdel qubes
fi

%files
%defattr(-,root,root,-)
%config(noreplace) %attr(0664,root,qubes) %{_sysconfdir}/qubes/qmemman.conf
%config(noreplace) /etc/dbus-1/system.d/org.qubesos.PolicyAgent.conf
/usr/bin/qvm-*
/usr/bin/qubes-*
/usr/bin/qmemmand
/usr/bin/qubesd*
/usr/bin/qrexec-policy
/usr/bin/qrexec-policy-agent

%{_mandir}/man1/qubes*.1*

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
%{python3_sitelib}/qubes/exc.py
%{python3_sitelib}/qubes/firewall.py
%{python3_sitelib}/qubes/log.py
%{python3_sitelib}/qubes/rngdoc.py
%{python3_sitelib}/qubes/tarwriter.py
%{python3_sitelib}/qubes/utils.py

%dir %{python3_sitelib}/qubes/api
%dir %{python3_sitelib}/qubes/api/__pycache__
%{python3_sitelib}/qubes/api/__pycache__/*
%{python3_sitelib}/qubes/api/__init__.py
%{python3_sitelib}/qubes/api/internal.py
%{python3_sitelib}/qubes/api/admin.py

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
%{python3_sitelib}/qubes/tools/qubesd.py
%{python3_sitelib}/qubes/tools/qubesd_query.py
%{python3_sitelib}/qubes/tools/qvm_backup.py
%{python3_sitelib}/qubes/tools/qvm_backup_restore.py

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

%{python3_sitelib}/qubes/tests/api_admin.py
%{python3_sitelib}/qubes/tests/app.py
%{python3_sitelib}/qubes/tests/devices.py
%{python3_sitelib}/qubes/tests/events.py
%{python3_sitelib}/qubes/tests/firewall.py
%{python3_sitelib}/qubes/tests/init.py
%{python3_sitelib}/qubes/tests/storage.py
%{python3_sitelib}/qubes/tests/storage_file.py
%{python3_sitelib}/qubes/tests/storage_kernels.py
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
%{python3_sitelib}/qubes/tests/tools/qubesd.py

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

%dir %{python3_sitelib}/qubes/qmemman
%dir %{python3_sitelib}/qubes/qmemman/__pycache__
%{python3_sitelib}/qubes/qmemman/__pycache__/*
%{python3_sitelib}/qubes/qmemman/__init__.py
%{python3_sitelib}/qubes/qmemman/algo.py
%{python3_sitelib}/qubes/qmemman/client.py

%dir %{python3_sitelib}/qubespolicy
%dir %{python3_sitelib}/qubespolicy/__pycache__
%{python3_sitelib}/qubespolicy/__pycache__/*
%{python3_sitelib}/qubespolicy/__init__.py
%{python3_sitelib}/qubespolicy/cli.py
%{python3_sitelib}/qubespolicy/agent.py
%{python3_sitelib}/qubespolicy/gtkhelpers.py
%{python3_sitelib}/qubespolicy/rpcconfirmation.py
%{python3_sitelib}/qubespolicy/utils.py

%dir %{python3_sitelib}/qubespolicy/tests
%dir %{python3_sitelib}/qubespolicy/tests/__pycache__
%{python3_sitelib}/qubespolicy/tests/__pycache__/*
%{python3_sitelib}/qubespolicy/tests/__init__.py
%{python3_sitelib}/qubespolicy/tests/gtkhelpers.py
%{python3_sitelib}/qubespolicy/tests/rpcconfirmation.py

%dir %{python3_sitelib}/qubespolicy/glade
%{python3_sitelib}/qubespolicy/glade/RPCConfirmationWindow.glade

/usr/lib/qubes/cleanup-dispvms
/usr/lib/qubes/fix-dir-perms.sh
/usr/lib/qubes/startup-misc.sh
/usr/libexec/qubes/qubes-notify-tools
/usr/libexec/qubes/qubes-notify-updates
/usr/libexec/qubes/qubesd-query-fast
%{_unitdir}/qubes-core.service
%{_unitdir}/qubes-netvm.service
%{_unitdir}/qubes-qmemman.service
%{_unitdir}/qubes-vm@.service
%{_unitdir}/qubesd.service
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
/etc/xen/scripts/block-snapshot
/etc/xen/scripts/block-origin
/etc/xen/scripts/vif-route-qubes
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/admin.*
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/include/admin-all
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.FeaturesRequest
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.Filecopy
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.GetImageRGBA
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.GetRandomizedTime
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.NotifyTools
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.NotifyUpdates
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.OpenInVM
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.OpenURL
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.VMShell
%attr(0664,root,qubes) %config(noreplace) /etc/qubes-rpc/policy/qubes.UpdatesProxy
/etc/qubes-rpc/admin.*
/etc/qubes-rpc/qubes.FeaturesRequest
/etc/qubes-rpc/qubes.GetRandomizedTime
/etc/qubes-rpc/qubes.NotifyTools
/etc/qubes-rpc/qubes.NotifyUpdates
%attr(2770,root,qubes) %dir /var/log/qubes
%attr(0770,root,qubes) %dir /var/run/qubes
/etc/xdg/autostart/qrexec-policy-agent.desktop

/usr/share/doc/qubes/relaxng/*.rng
