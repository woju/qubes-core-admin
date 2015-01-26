.. program:: qvm-service

========================================================================
:program:`qvm-service` -- Manage (Qubes-specific) services started in VM
========================================================================

Synopsis
========
| :command:`qvm-service` [-l] <*vmname*>
| :command:`qvm-service` [-e|-d|-D] <*vmname*> <*service*>

Options
=======
.. option:: --help, -h

    Show this help message and exit

.. option:: --list, -l

    List services (default action)

.. option:: --enable, -e

    Enable service

.. option:: --disable, -d

    Disable service

.. option:: --default, -D

    Reset service to its default state (remove from the list). Default state
    means "lets VM choose" and can depend on VM type (NetVM, AppVM etc).

Supported services
==================

This list can be incomplete as VM can implement any additional service without
knowledge of qubes-core code.

meminfo-writer
    Default: enabled everywhere excluding NetVM

    This service reports VM memory usage to dom0, which effectively enables
    dynamic memory management for the VM.

    .. note::

        This service is enforced to be set by dom0 code. If you try to
        remove it (reset to default state), will be recreated with the rule: enabled
        if VM have no PCI devices assigned, otherwise disabled.

qubes-firewall
    Default: enabled only in ProxyVM

    Dynamic firewall manager, based on settings in dom0 (qvm-firewall, firewall
    tab in qubes-manager)

qubes-network
    Default: enabled only in NetVM and ProxyVM

    Expose network for other VMs. This includes enabling network forwarding,
    MASQUERADE, DNS redirection and basic firewall.

qubes-netwatcher
    Default: enabled only in ProxyVM

    Monitor IP change notification from NetVM. When received, reload
    qubes-firewall service (to force DNS resolution).

    This service makes sense only with qubes-firewall enabled.

qubes-update-check
    Default: enabled

    Notify dom0 about updates available for this VM. This is shown in
    qubes-manager as 'update-pending' flag.

cups
    Default: enabled only in AppVM

    Enable CUPS service. The user can disable cups in VM which do not need
    printing to speed up booting.

network-manager
    Default: enabled in NetVM

    Enable NetworkManager. Only VM with direct access to network device needs
    this service, but can be useful in ProxyVM to ease VPN setup.

qubes-yum-proxy
    Default: enabled in NetVM

    Provide proxy service, which allow access only to yum repos. Filtering is
    done based on URLs, so it shouldn't be used as leak control (pretty easy to
    bypass), but is enough to prevent some erroneous user actions.

yum-proxy-setup
    Default: enabled in AppVM (also in templates)

    Setup yum at startup to use qubes-yum-proxy service.

    .. note::

       this service is automatically enabled when you allow VM to access yum
       proxy (in firewall settings) and disabled when you deny access to yum
       proxy.


Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
