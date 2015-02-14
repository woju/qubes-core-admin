# Qubes R2 LVM Thin Support

This is patch set improves performance and saves a tone of hard disk space by managing vm images as thin snapshots. Currently Qubes uses files as devices for the vms. This is a peaty neat but slow and fat solution. 

Fedora 20 ships with lvm thin provisioning, you can even choose an LVM+Thin based harddrive setup when installing Qubes. LVM provides quite a few interesting features:
 * thin provisioning (over-committing storage)
 * writable snapshot support
 * volume types with different storage allocation methods

### Example Use Case
Clone  your default template as `fedora-20-x64-dev` template. Install the default Fedora development tools in it. Now create more specialized templates based on it with tools you need on day-to-day basis i.e:
 * fc20-go
 * fc20-java
 * fc20-python
 * fc20-rails
 * fc20-branfuck

Each template only costs the little bit extra space for the specific tools and not 10Gb like currently, because each time you clone a vm the private and root image are created as **thin** snapshots. You can read more about LVM on [Gentoo Wiki](http://wiki.gentoo.org/wiki/LVM#Creating_a_thin_pool)

## State 
The current implementation is the fourth incarnation working on my daily used workstation. All the basic operations work (See also *Implemented Features* list). After the installation you can still use your old file based VM images. All operations on file based images work like before.

## Installation
* Make sure you have a volume group named `qubes_dom0` and a thin pool called `pool0` (default Qubes values)
* Setup your [development vm](https://wiki.qubes-os.org/wiki/DevelopmentWorkflow). 
* Set `GIT_PREFIX` to `qubes-r2/` in `builder.conf`
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
  `qvm-clone fedora-20-x64 fc20` 
Migrate the created vm to lvm:
 `qvm-to-lvm f20` 

Now each time you clone this vm or create a vm based on it `core-admin` will use LVM as backend. You can migrate any vm (DisplayVM work in progress). 

### Note: 
* When you migrate an AppVM to lvm which is based on a file based template only private is migrated
* When you migrate a TemplateVM all already existing AppVMs based on it will still use files for private
* You need *manualy* remove `root.img` and `private.img` file. `qvm-to-lvm` preserves this files!
* You need to to apply [this change](https://github.com/kalkin/qubes-manager/commit/6b5e8113695893264b527095a23c222196fc5fd1) to `/usr/lib64/python2.7/site-packages/qubesmanager/settings.py` (or build rpm from the repo)

## How can i help?

You can build and install this patch set. Use it, Play with it, Report bugs and submit Patches. My Goal is someday to get thin snapshot support in qubes. I do not want to maintain my own patch set for ever (but i will if i have to).



## Implementation Details

### qvm-to-lvm
 The `qvm-to-lvm` tool is used to migrate a file based vm to LVM. It uses the lvm pool `qubes_dom0/pool0`, which is the default for qubes lvm+thin installation.  When  migrating a template based VM only the `private.img` device is migrated. The vm will use the "old way" for booting from file based root snapshot. 

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

### Implemented Features
 * [x] file image to lvm import tool [qvm-to-lvm](/qvm-tools/qvm-to-lvm)
 * [x] Backported storage implementation from qubes-r3
 * [x] Reimplemented the file storage based operations
 * [x] Cloning of AppVMs
 * [x] Creation/Cloning of TemplateVMs 
 * [x] Creation/Cloning of Standalone / HVM(?) machines
 * [x] Storage verification (hacky but stable)
 * [x] Rename and Removale of VMs based on LVM

### Work in Progress
 * [ ] Fix is_outdated() check for LVM (use tune2fs?)
 * [ ] extend Support for LVM (for now only manual via `lvextend`)
 * [ ] Fix setting autoboot in QubesManager (currently not possible via QubesManager)
 * [ ] DisplayVM Support is missing. (You still can use DisplayVMs based om normal Qubes images)
 * [ ] LVM will snapshot or clone an VM even if it's running. This is should not be an issue in most cases, but should be fixed (?)
 * [ ] Come up with better naming scheme for volumes.
 * [ ] QubesManager should hide the mounted private and root image `Attach/Detach block devices`

### Backups
Backups of LVM based vms should probably work but i have not tested it yet.  I personally use dirvish + thin snapshots + hard links on an encrypted device.
