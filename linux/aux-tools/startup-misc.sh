#!/bin/sh

# Misc dom0 startup setup

/usr/lib/qubes/fix-dir-perms.sh
xenstore-write /local/domain/0/name dom0
xenstore-write domid 0
DOM0_MAXMEM=`/usr/sbin/xl info | grep total_memory | awk '{ print $3 }'`
xenstore-write /local/domain/0/memory/static-max $[ $DOM0_MAXMEM * 1024 ]

xl sched-credit -d 0 -w 512
cp /var/lib/qubes/qubes.xml /var/lib/qubes/backup/qubes-$(date +%F-%T).xml

/usr/lib/qubes/cleanup-dispvms

# Hide mounted devices from qubes-block list (at first udev run, only / is mounted)
udevadm trigger --action=change --subsystem-match=block
