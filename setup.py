#!/usr/bin/python2 -O
# vim: fileencoding=utf-8

import glob
import os
import setuptools

# don't import: import * is unreliable and there is no need, since this is
# compile time and we have source files
def get_console_scripts():
    for filename in os.listdir('./qubes/tools'):
        basename, ext = os.path.splitext(os.path.basename(filename))
        if basename == '__init__' or ext != '.py':
            continue
        yield '{} = qubes.tools.{}:main'.format(
            basename.replace('_', '-'), basename)

if __name__ == '__main__':
    setuptools.setup(
        name='qubes',
        version=open('version').read().strip(),
        author='Invisible Things Lab',
        author_email='woju@invisiblethingslab.com',
        description='Qubes core package',
        license='GPL2+',
        url='https://www.qubes-os.org/',

        packages=setuptools.find_packages(exclude=('core*', 'tests')),

        entry_points={
            'console_scripts': list(get_console_scripts()),
        }
    )
