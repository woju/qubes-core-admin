#!/bin/bash

set -o pipefail

get_encoded_script()
{
	ENCODED_SCRIPT=`
		if [ "$1" == "vm-default" ]; then
			echo /usr/lib/qubes/dispvm-prerun.sh
		else
			cat "$1"
		fi | base64 -w0` || exit 1
}

if [ $# != 2 -a $# != 3 ] ; then
	echo usage: $0 domainname savefile_to_be_created [preload script]
	exit 1
fi
export PATH=$PATH:/sbin:/usr/sbin
if [ $# = 3 ] ; then
	get_encoded_script $3
fi
VMDIR=/var/lib/qubes/appvms/$1
if ! [ -d $VMDIR ] ; then
	echo $VMDIR does not exist ?
	exit 1
fi
if ! qvm-start $1 --no-guid --dvm ; then
	exit 1
fi

echo "Waiting for DVM $1 ..."
if [ -n "$ENCODED_SCRIPT" ] ; then
	qubesdb-write -d $1 /qubes-save-script "$ENCODED_SCRIPT"
fi
#set -x
qubesdb-write -d $1 /qubes-save-request 1
qubesdb-watch -d $1 /qubes-used-mem
qubesdb-read -d $1 /qubes-gateway | \
	cut -d . -f 3 | tr -d "\n" > $VMDIR/netvm-id.txt
# FIXME: get connection URI from core scripts
virsh -c xen:/// detach-disk $1 xvdb
MEM=$(qubesdb-read -d $1 /qubes-used-mem)
echo "DVM boot complete, memory used=$MEM. Saving image..."
QMEMMAN_STOP=/var/run/qubes/do-not-membalance
touch $QMEMMAN_STOP
virsh -c xen:/// setmem $1 $MEM
# Add some safety margin
virsh -c xen:/// setmaxmem $1 $[ $MEM + 1024 ]
# Stop qubesdb daemon now, so VM can restart it later
kill `cat /var/run/qubes/qubesdb.$1.pid`
sleep 1
touch $2
if ! virsh -c xen:/// save $1 $2; then
	rm -f $QMEMMAN_STOP
	exit 1
fi
rm -f $QMEMMAN_STOP
ln -s $VMDIR /var/lib/qubes/dvmdata/vmdir
cd $VMDIR
tar -Scvf saved-cows.tar volatile.img
echo "DVM savefile created successfully."
