#!/usr/bin/python2 -O
# vim: fileencoding=utf-8

import os.path
import qubes
import qubes.vm.qubesvm

class TemplateVM(qubes.vm.qubesvm.QubesVM):
    '''Template for AppVM'''

    def __init__(self, *args, **kwargs):
        super(TemplateVM, self).__init__(*args, **kwargs)

        # Some additional checks for template based VM
        assert self.root_img is not None, "Missing root_img for standalone VM!"

    @property
    def rootcow_img(self):
        return os.path.join(self.dir_path, qubes.config.vm_files['rootcow_img'])


