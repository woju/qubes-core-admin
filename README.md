# Qubes R3.1 LVM Thin Support

This is patchset improves performance and saves a tone of hard disk space by
managing domain images as thin snapshots. Currently Qubes uses files as devices for
the domains. This is a pretty neat but slow and fat solution. 

Fedora 20 ships with lvm thin provisioning, you can even choose an LVM+Thin
based hard drive setup when installing Qubes. LVM also provides quite a few
interesting features:
 * thin provisioning (over-committing storage)
 * writable snapshot support with decent performance
 * volume types with different storage allocation methods

### Example Use Case
Clone  your default template as `fedora-23` template. Install the default Fedora
development tools in it. Now create more specialized templates based on it with
tools you need on day-to-day basis i.e:
 * fc23-go
 * fc23-java
 * fc23-python
 * fc23-rails
 * fc23-branfuck

Each template only costs the little bit extra space for the specific tools and
not 10Gb like currently, because each time you clone a domain the private and root
image are created as **thin** snapshots. You can read more about LVM on [Gentoo
Wiki](http://wiki.gentoo.org/wiki/LVM#Creating_a_thin_pool)

This way you can now create an own domain for each of your python project.

## State 
The current implementation is the fifth incarnation working on my daily used
workstation. All the basic operations work (See also *Implemented Features*
list). After the installation you can still use your old file based VM
images. All operations on file based images work like before.

## Installation
* Make sure you have a volume group named `qubes_dom0` and a thin pool called `pool0` (default Qubes values)
* Setup your [development vm](https://wiki.qubes-os.org/wiki/DevelopmentWorkflow). 
* Set `COMPONENT` in `builder.conf` to `core-admin`.
* `make get-source`
* Add this repository as remote remote for `qubes-src/core-admin`. 
```
$ cd qubes-src/core-admin 
$ git remote add lvm https://github.com/kalkin/qubes-core-admin.git
```
 * Set `GIT_REMOTE` to `http://github.com/kalkin/qubes-core-admin/`
 * `make get-source`
 * `make core-admin`
 * Copy created `qubes-src/core-admin/rpm/x86_64/qubes-core-dom0-2.1.68.3-1.fc20.x86_64.rpm` to your dom0 and install it

## Usage
Clone your default template (just to be sure and dvms need it):
  `qvm-clone fedora-23-x64 fc23` 
Migrate the created vm to lvm by using dd and adjusting qubes.xml config 

Now each time you clone this vm or create a vm based on it `core-admin` will use
LVM as backend. You can migrate any vm (DisplayVM work in progress). 

## How can i help?

You can build and install this patch set. Use it, Play with it, Report bugs and submit Patches. My Goal is someday to get thin snapshot support in qubes. I do not want to maintain my own patch set for ever (but i will if i have to).

## Implementation Details

### lvm.py
The [lvm](/core/storage/lvm.py) module implements all the lvm logic.  At the moment it just calls the `sudo lv*` commands. There is a python lvm module, while it is useful it is just simpler to use `sudo`. (How can you manage lvm without being root?)

### core-modules
Moved most storage code to storage. In `qubes.xml` `storage_type` is set to `file` or `lvm`.

### Naming Conventions

 * The root image is always called vmname-root
 * The private image is always called vmname-private
 *

### Templated based VMs

A vm named `netvm` and based on `fc2-min` will try to remove `/dev/qubes_dom0/netvm-root` and create a new snapshot with the same name based on `/dev/qubes_dom0/fc20-min`
