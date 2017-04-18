:py:mod:`qubes.mgmt` -- Qubes remote API
========================================

Qubes OS can be remotely managed using `Qubes Management API
<https://www.qubes-os.org/doc/mgmt1/>`_. This qrexec-based API is available to
domains as specified in qrexec policy. Typically only select domains will be
able to manage the system. There are two main use cases: GUI domain and remote
management.

The API is also used internally for management within the admin qube.

This page will discuss the implementation. For specification, see the page in
the official Qubes OS documentation.

Qubesd
------

:program:`qubesd` is a daemon which is responsible for dispatching everything
what happens. It receives connection from qrexec API as well as listens for
events in :program:`libvirtd`. Also it has facility to serve other processes
inside ``dom0``. :program:`qubesd` is long lived, contrary to previous ``qvm-*``
tools. It is written using :py:mod:`asyncio` framework.

Internally, :program:`qubesd` listens on several sockets. They share common data
format, but they serve different set on API calls. This is to separate methods
available from outside of ``dom0`` from the methods for internal use by
:program:`qmemmand` and qrexec policy query. The program :program:`qubesd-query`
can be used to send an API call using common format.

:program:`qubesd` consists of three main classes:
:py:class:`qubes.tools.qubesd.QubesDaemonProtocol`, which is responsible for
parsing incoming requests, and :py:class:`qubes.mgmt.QubesMgmt`, which contains
implementation of the methods in public API.

.. todo::

    There will be a third class for the internal socket. The name is not yet
    decided.

How to write a new API method
-----------------------------

You have to define new method in :py:class:`qubes.mgmt.QubesMgmt`. It has to be
named as the API call, with the following exceptions: ``'mgmt.'`` is stripped
from the front, dots (``'.'``) are replaced with underscores (``'_'``) and all
letters are converted to lower case.

The class instance has useful attributes. Three of them are parsed from the API
call: :py:attr:`qubes.mgmt.QubesMgmt.src`, :py:attr:`qubes.mgmt.QubesMgmt.dest`
and :py:attr:`qubes.mgmt.QubesMgmt.arg`. Their values are trusted, since they
were allowed by qrexec policy. There is also
:py:attr:`qubes.mgmt.QubesMgmt.app`, which is global :py:class:`qubes.app.Qubes`
object. Last but not least, there are two methods which are used for querying
plugins for fine-grained access control:
:py:meth:`qubes.mgmt.QubesMgmt.fire_event_for_permission` and 
:py:meth:`qubes.mgmt.QubesMgmt.fire_event_for_filter`. Both of those fire an
event on the source qube object (possibly ``dom0``), which can be used by
extensions to control access to the call. The signature of the event is up to
the implementer of the particular API.

Your method should accept one argument: ``untrusted_payload``. It will be called
as keyword argument to ensure that it is named such. This is to remind the
programmer that the content is untrusted (it very well can be malicious), so you
have to take extra care while processing it. In no instance it should be passed
verbatim outside this function, including to
:py:meth:`qubes.mgmt.QubesMgmt.fire_event_for_permission`.

Your function should perform these steps:

1. ``assert`` everything you know about the arguments. Even if you do not use
   the content of some variable and expect it to be empty, you should ``assert``
   that anyway, to combat attacks against protocol framing.
2. Either ``del untrusted_payload`` or perform validation on it.
3. :py:meth:`qubes.mgmt.QubesMgmt.fire_event_for_permission`.
4. Perform any desired operations.
5. ``return`` the response which will be sent back to the caller.

.. code-block:: python

    class QubesMgmt(object):
        # ...
        def example_echo(self, untrusted_payload):
            '''Can be called as mgmt.example.Echo

            But only if payload starts with "Hello, ".
            '''

            #
            # 1. assert everything we know
            #
            assert self.dest is self.app.domains['dom0']
            assert not self.arg

            #
            # 2. validate payload
            #

            # this will barf if there are characters > 127
            untrusted_payload = untrusted_payload.decode('ascii')

            # all characters have to be printable
            assert all(0x20 <= c < 0x7f for c in untrusted_payload)

            # like docstring says, we serve only gentelmen
            assert untrusted_payload.startswith('Hello, ')

            # no we know everything we wanted
            payload = untrusted_payload
            del untrusted_payload

            #
            # 3. as for permission
            #
            self.fire_event_for_permission(payload=payload)

            #
            # 4. perform operation
            #
            self.dest.features['example-echo-fired'] = '1'

            #
            # 5. return some response
            #
            return payload


How to write API access control extension
-----------------------------------------

You have to hook an event ``'mgmt-permission:mgmt.example.Method'`` fired on the
source qube. Those events are fired with a signature dependent on a particular
call. In principle any call will pass different pre-parsed information just
before actually executing the intended operation. If you would like to deny the
call, you should ``raise`` :py:exc:`qubes.mgmt.PermissionDenied`. If you'd like
to permit, just do nothing (that is, ``return None``).

Some API calls will :py:meth:`qubes.mgmt.QubesMgmt.fire_event_for_filter`. The
event name is the same. In such cases you can either ``raise``
:py:exc:`qubes.mgmt.PermissionDenied` to wholesale deny the call, like in
previous case, or not raise the exception and return a decision function. Of
course you can also do nothing and ``return None``, which indicates wholesale
acceptance. This is intended for method listing something, like domains or
properties: for example you can list only some of the domains to a specific
management qube.

The decision function should take one parameter: the object being filtered. If
the function returns logical false, the item in question will be removed from
the list of considered objects. If employed, all filtering functions should
agree, that is, if any filtering function returns :py:obj:`False`, the object is
denied. There is no guarantee that all filtering functions will be called for
all objects, and some may be optimised out if a function from other extension
already returned :py:obj:`False`.

.. code-block:: python

    import qubes.ext
    class QubesExampleACLExtension(qubes.ext.Extension):
        @qubes.ext.handler('mgmt-permission:mgmt.vm.List')


Module contents
---------------

.. automodule:: qubes.mgmt
   :members:
   :show-inheritance:

.. vim: ts=4 sts=4 sw=4 et
