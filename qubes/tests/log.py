#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
'''
Qubes OS - Logging Tests

:copyright: © 2010-2014 Invisible Things Lab

@author: Jason Mehring
'''

__author__ = 'Invisible Things Lab'
__license__ = 'GPLv2 or later'
__version__ = 'R3'

import os
import sys
import unittest
import logging
import tempfile
import textwrap

import qubes.log
import qubes.tests


QUBES_PATH = qubes.__path__[0]

def write_temp_file(data, suffix='.json'):
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as outfile:
        filename = outfile.name
        outfile.write(str(data))
        return outfile.name


class TC_00_getConfiguration(qubes.tests.QubesTestCase):
    def test_000_getConfiguration_cache(self):
        filenames = []
        filenames.append(write_temp_file({}))
        filenames.append(write_temp_file({}))
        filenames.append(write_temp_file({}))
        for filename in filenames:
            logging.root.handlers = []
            qubes.log.getConfiguration(filename=filename)
            os.unlink(filename)
        config = qubes.log.getConfiguration._instance.keys()
        for filename in filenames:
            self.assertEquals(filename in config, True,
                'getConfiguration failed to cache {0}'.format(filename))


class TC_99_Functions(qubes.tests.QubesTestCase):
    def test_000_ansi_text(self):
        result = qubes.log.ansi_text(text='Foobar')
        self.assertEqual(result, 'Foobar', 'Ansi failed to colorize')

    def test_001_ansi_text_colors(self):
        result = qubes.log.ansi_text(text='Foobar', colors=['blue', 'inverse'])
        self.assertEqual(
            result, '\x1b[34m\x1b[7mFoobar\x1b(B\x1b[m', 'Ansi failed to colorize')

    def test_002_get_configuration_correct_config_filename(self):
        filename = os.path.join(QUBES_PATH, 'log.json')
        config = qubes.log.get_configuration(filename=filename)
        self.assertEquals(
            '_ERROR_' in config, False, 'Configuration file failed to load')

    def test_003_get_configuration_incorrect_config_filename(self):
        config = qubes.log.get_configuration(
            filename='path_does_not_exist.yaml')
        self.assertEquals('_ERROR_' in config.keys(), True,
            'Default logger should have been enabled but received a value of True')

    def test_004_get_configuration_parse_error(self):
        config_fail = '''\
        root:
            level: INFO
          handlers: [color_console, info_file_handler]
        '''
        filename = write_temp_file(textwrap.dedent(config_fail))
        logging.root.handlers = []
        config = qubes.log.get_configuration(filename=filename)
        self.assertEquals('_ERROR_' in config, True,
            'Default logger should have been enabled but received a value of True')
        os.unlink(filename)

    def test_005_get_configuration_env_config_filename(self):
        filename = os.path.join(QUBES_PATH, 'log.json')
        os.environ['LOG_CONFIG_FILENAME_TEST'] = filename
        config = qubes.log.get_configuration(
            env_key='LOG_CONFIG_FILENAME_TEST')
        self.assertEquals(
            '_ERROR_' in config, False, 'Configuration file failed to load')


def main():
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    return runner.run(suite).wasSuccessful()

if __name__ == '__main__':
    sys.exit(not main())
