#!/usr/bin/env python3.6

import asyncio
import functools
import io
import os
import shutil
import signal
import struct
import traceback

import libvirtaio

import qubes
import qubes.api
import qubes.api.admin
import qubes.api.internal
import qubes.utils
import qubes.vm.qubesvm


def sighandler(loop, signame, servers):
    print('caught {}, exiting'.format(signame))
    for server in servers:
        server.close()
    loop.stop()

parser = qubes.tools.QubesArgumentParser(description='Qubes OS daemon')
parser.add_argument('--debug', action='store_true', default=False,
    help='Enable verbose error logging (all exceptions with full '
         'tracebacks) and also send tracebacks to Admin API clients')

def main(args=None):
    loop = asyncio.get_event_loop()
    libvirtaio.virEventRegisterAsyncIOImpl(loop=loop)
    try:
        args = parser.parse_args(args)
    except:
        loop.close()
        raise

    args.app.vmm.register_event_handlers(args.app)

    servers = []
    servers.append(loop.run_until_complete(qubes.api.create_server(
        qubes.api.admin.QUBESD_ADMIN_SOCK,
        qubes.api.admin.QubesAdminAPI,
        app=args.app, debug=args.debug)))
    servers.append(loop.run_until_complete(qubes.api.create_server(
        qubes.api.internal.QUBESD_INTERNAL_SOCK,
        qubes.api.internal.QubesInternalAPI,
        app=args.app, debug=args.debug)))

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame),
            sighandler, loop, signame, servers)

    qubes.utils.systemd_notify()
    # make sure children will not inherit this
    os.environ.pop('NOTIFY_SOCKET', None)

    try:
        loop.run_forever()
        loop.run_until_complete(asyncio.wait([
            server.wait_closed() for server in servers]))
    finally:
        loop.close()

if __name__ == '__main__':
    main()
