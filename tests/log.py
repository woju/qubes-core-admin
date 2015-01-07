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
import logging
import unittest

import qubes.log


class Test(unittest.TestCase):

    def test_ansi_text(self):
        result = qubes.log.ansi_text(text='Foobar')
        self.assertEqual(result, 'Foobar', 'Ansi failed to colorize')

    def test_ansi_text_colors(self):
        result = qubes.log.ansi_text(
            text='Foobar', **{'color': 'blue', 'inverse': True})
        self.assertEqual(
            result, '\x1b[7;34mFoobar\x1b[0m', 'Ansi failed to colorize')

    def test_get_configuration_correct_config_filename(self):
        config = qubes.log.get_configuration(filename='qubes/log.yaml')
        self.assertEquals(
            '__ERROR__' in config, False, 'Configuration file failed to load')

    def test_get_configuration_incorrect_config_filename(self):
        config = qubes.log.get_configuration(
            filename='path_does_not_exist.yaml')
        self.assertEquals('__ERROR__' in config, True,
            'Default logger should have been enabled but received a value of True')

    def test_get_configuration_parse_error(self):
        logging.root.handlers = []
        config = qubes.log.get_configuration(filename='/bin/true')
        self.assertEquals( '__ERROR__' in config, True,
            'Default logger should have been enabled but received a value of True')

    def test_get_configuration_env_config_filename(self):
        os.environ['LOG_CONFIG_FILENAME_TEST'] = 'qubes/log.yaml'
        config = qubes.log.get_configuration(env_key='LOG_CONFIG_FILENAME_TEST')
        self.assertEquals(
            '__ERROR__' in config, False, 'Configuration file failed to load')

if __name__ == '__main__':
    unittest.main()
