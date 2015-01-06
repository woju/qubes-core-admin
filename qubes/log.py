#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-

# autopep8 --ignore E309 -a -i

'''Qubes logging routines

See also: :py:attr:`qubes.vm.qubesvm.QubesVM.logger`
'''

import os
import sys
import re
import copy
import collections
import logging.config
import yaml

from yaml.parser import ParserError
from yaml.reader import ReaderError

# Logging filename
LOG_FILENAME = '/var/log/qubes/qubes.log'

# Logging configuration file
CONFIG_FILENAME = os.path.join(os.path.dirname(__file__), 'log.yaml')

CONFIG = {
    'LOGFILE': LOG_FILENAME,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': 'CONS: %(message)s'},
        'simple': {
            'format': 'SIMP %(asctime)s - %(levelname)8s - %(message)s'},
        'info': {
            'format': 'INFO: %(asctime)s%(levelname)8s: %(name)s:[%(processName)s %(module)s.%(funcName)s:%(lineno)d]: %(message)s'},
        'debug': {
            'format': 'DEBU: %(asctime)s%(levelname)8s: %(name)s:[%(processName)s %(module)s.%(funcName)s:%(lineno)d]: %(message)s'},
    },
    'handlers': {
        'info_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'},
        'debug_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'debug',
            'stream': 'ext://sys.stdout'},
        'info_file_handler': {
            'backupCount': 5,
            'class': 'logging.handlers.RotatingFileHandler',
            'encoding': 'utf8',
            'filename': LOG_FILENAME,
            'formatter': 'info',
            'maxBytes': 10485760},
        'debug_file_handler': {
            'backupCount': 5,
            'class': 'logging.handlers.RotatingFileHandler',
            'encoding': 'utf8',
            'filename': LOG_FILENAME,
            'formatter': 'debug',
            'maxBytes': 10485760},
    },
    'root': {
        'handlers': [
            'info_console',
            'info_file_handler'],
        'level': 'INFO'},
    'version': 1}

ANSI_COLORS = {
    ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
    [i]: i for i in range(8)
}


def enable(config_filename=CONFIG_FILENAME, level=logging.INFO,
           env_key='LOG_CONFIG_FILENAME'):
    '''Enable global logging

    Uses a YAML configuration file to set any configuration details

    :param str config_filename: YAML logging configuration filename
    :param int level: Logging level.  IE: 20 or logging.INFO
    :param str env_key: Environment key containing configuration filename
    :returns: Returns True if configuration file was successfully used or False if default values were used
    :rtype: boolean

    Use :py:mod:`logging` module from standard library to log messages.

    >>> import qubes.log
    >>> qubes.log.enable()          # doctest: +SKIP
    >>> import logging
    >>> logging.warning('Foobar')   # doctest: +SKIP
    '''

    # Logging has already been enabled, return
    if logging.root.handlers:
        return

    config = get_configuration(config_filename, env_key)
    logging.config.dictConfig(config)

    # Log error that configuration file could not be found / used
    if '__ERROR__' in config.keys():
        logging.warn(config.get('_ERROR_', 'Default Configuration Enabled!'))


def enable_debug(
        config_filename=CONFIG_FILENAME,
        env_key='LOG_CONFIG_FILENAME'):
    '''Enable debug logging

    Enable more messages and additional info to message format.
    '''
    config = get_configuration(config_filename, env_key)

    for logger in config.get('loggers', {}).keys():
        config['loggers'][logger]['level'] = 'DEBUG'
        config['loggers'][logger]['handlers'] = [
            'debug_console',
            'debug_file_handler']

    config['root']['level'] = 'DEBUG'
    config['root']['handlers'] = ['debug_console', 'debug_file_handler']

    logging.config.dictConfig(config)

    # Log error that configuration file could not be found / used
    if '__ERROR__' in config.keys():
        logging.warn(config.get('_ERROR_', 'Default Configuration Enabled!'))


def get_vm_logger(
        vmname,
        config_filename=CONFIG_FILENAME,
        env_key='LOG_CONFIG_FILENAME'):
    '''Initialize logging for particular VM name

    :param str vmname: VM's name
    :rtype: :py:class:`logging.Logger`
    '''

    config = get_configuration(config_filename, env_key)
    log_path = os.path.dirname(config.get('LOG_FILENAME', LOG_FILENAME))
    filename = os.path.join(log_path, 'vm', vmname + '.log')

    logger = add_logger('vm.{0}'.format(vmname),
                        config,
                        level=logging.INFO,
                        filename=filename,
                        handlers=['info_file_handler']
                        )

    return logger


def get_configuration(filename=None, env_key=None):
    message = None

    # Use the configuration filename provided in environment if available
    if env_key:
        filename = os.getenv(env_key, filename)

    if filename and os.path.exists(filename):
        # Enabe logging with values in logging configuration file
        try:
            with open(filename, 'rt') as infile:
                config = yaml.load(infile.read())
        except (IOError, ParserError, ReaderError) as e:
            config = {
                '__ERROR__': 'Can not load logging configuration file, using defaults: {0}'.format(e)}
    else:
        config = {
            '__ERROR__': 'Can not find logging configuration file {0}. Using defaults.'.format(filename)}

    if '__ERROR__' in config.keys():
        config.update(CONFIG)

    return config


def add_logger(
        name,
        config,
        level=logging.INFO,
        filename=LOG_FILENAME,
        handlers=['info_file_handler'],
        propagate=0):
    if isinstance(handlers, str):
        handlers = [handlers]

    handlers = get_handlers(config, handlers, filename=filename)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = propagate
    for handler in handlers.values():
        logger.addHandler(handler)

    return logger


def get_formatter(config, formatter):
    config = copy.deepcopy(config)
    dict_configurator = logging.config.DictConfigurator({})

    formatter_dict = config.get('formatters', {}).get(formatter, {})
    try:
        formatter_dict = dict_configurator.configure_formatter(formatter_dict)
    except Exception:
        raise ValueError('Unable to configure '
                         'formatter %r: %s' % (formatter, e))
    return formatter_dict


def get_formatters(config):
    #config = copy.deepcopy(config)
    dict_configurator = logging.config.DictConfigurator({})

    formatters = config.get('formatters', {})
    for name in formatters:
        try:
            formatters[name] = dict_configurator.configure_formatter(
                formatters[name])
        except Exception:
            raise ValueError('Unable to configure '
                             'formatter %r: %s' % (name, e))
    return formatters


def get_handler(config, handler, **args):
    config = copy.deepcopy(config)
    dict_configurator = logging.config.DictConfigurator({})
    dict_configurator.config = config

    handler_dict = config.get('handlers', {}).get(handler, {})
    formatter = get_formatter(config, handler_dict.get('formatter', ''))

    # Override config value
    for key, value in args.items():
        if key in handler_dict:
            handler_dict[key] = value

    deferred = False
    try:
        result = dict_configurator.configure_handler(handler_dict)
        result.name = handler
        handler_dict = result
    except Exception as e:
        if 'target not configured yet' in str(e):
            deferred = True
        else:
            raise ValueError('Unable to configure handler '
                             '%r: %s' % (handler, e))

    # Now do any that were deferred
    if deferred:
        try:
            result = dict_configurator.configure_handler(handler_dict)
            result.name = handler
            handler_dict = result
        except Exception as e:
            raise ValueError('Unable to configure handler '
                             '%r: %s' % (handler, e))

    handler_dict.formatter = formatter
    return handler_dict


def get_handlers(config, handlers=None, **args):
    if handlers is None:
        handlers = config.get('handlers', {}).keys()

    results = {}
    for name in sorted(handlers):
        results[name] = get_handler(config, name, **args)

    return results


def ansi_text(text, color=None, bold=False, faint=False,
              underline=False, inverse=False, strike_through=False):
    '''
    Wrap text in ANSI escape codes.

    :param str text: Text string to wrap
    :param str color: Valid colors are ``black``, ``red``, ``green``,
        ``yellow``, ``blue``, ``magenta``, ``cyan``, ``white``, or ``None``
    :param boolean bold: Bold font
    :param boolean faint: Faint font
    :param boolean underline: Underline font
    :param boolean inverse: Inverse font
    :param boolean strike_through: Strike-through font
    :returns: wrapped ANSI escaped text
    :rtype: str
    '''

    code_map = collections.OrderedDict([('bold', 1),
                                        ('faint', 2),
                                        ('underline', 4),
                                        ('inverse', 7),
                                        ('strike-through', 9),
                                        ('color', 3),
                                        ])
    codes = []
    for name, code in code_map.iteritems():
        if locals().get(name, None):
            if name in ['color']:
                if color in ANSI_COLORS.keys():
                    codes.append('3%i' % ANSI_COLORS[color])
            else:
                codes.append(str(code))

    if codes:
        return '\x1b[%sm%s\x1b[0m' % (';'.join(codes), text)
    else:
        return text


def lower(dictionary):
    '''
    '''

    for key, value in dictionary.iteritems():
        if key != key.lower():
            dictionary[key.lower()] = dictionary.pop(key)
        if isinstance(value, collections.Mapping):
            lower(value)
        elif isinstance(value, str):
            dictionary[key.lower()] = value.lower()
    return dictionary


class ColorFormatter(logging.Formatter):
    '''
    '''

    def __init__(self, fmt=None, datefmt=None, colors=None,
                 dynamic_labels=None):

        if not colors:
            self.colors = {}
            self._colorized = True
        else:
            self.colors = lower(colors)
            self._colorized = False

        self.dynamic_labels = ['levelname', ]
        if dynamic_labels:
            self.dynamic_labels.extend(dynamic_labels)

        logging.Formatter.__init__(self, fmt=fmt, datefmt=datefmt)
        self._template = {'_master': copy.copy(self._fmt)}

    def format(self, record):
        # Copy the original record so we don't break other handlers.
        record = copy.copy(record)

        if self.colors:
            # Caches by loglevel
            if logging.getLevelName(
                    record.levelno).lower() in self._template.keys():
                self._fmt = self._template[
                    logging.getLevelName(record.levelno).lower()]

            else:
                # Colourize existing 'template' once to reduce calls in colorizing
                # with the exception of fields that are dynamicly colored
                self.colourize(record)
                self._template[
                    logging.getLevelName(record.levelno).lower()] = copy.copy(
                    self._fmt)

        return logging.Formatter.format(self, record)

    def colourize(self, record):
        '''
        '''
        if not self._colorized and self.colors:
            for label in record.__dict__:

                if label not in self.colors.keys(
                ) or label in self.dynamic_labels:
                    # Add label to dynamic list if its color codes in levelname dict
                    # This alloes coloring the label same color as level color
                    if label in self.colors.get('levelname', {}).keys():
                        self.dynamic_labels.append(label)
                    else:
                        continue

                search_re = r'^.*(?P<label>%[(]\s*?{0}\s*[)].*?[diouxXeEfFgGcrs%]).*'.format(
                    label)
                match = re.match(search_re, self._fmt)

                if not match:
                    continue

                value = getattr(record, label, None)

                if label in self.dynamic_labels:
                    # colors = self.colors.get(label, {}).get(value.lower(), {})
                    colors = self.colors.get('levelname', {}).get(
                        logging.getLevelName(record.levelno).lower(), {})
                else:
                    colors = self.colors.get(label, {})

                if label in ['levelname']:
                    value = value.upper()

                if colors:
                    text = match.group('label')
                    text = ansi_text(text=text, **colors)
                    replace_re = r'(%[(]\s*?{0}\s*[)].*?[diouxXeEfFgGcrs%])'.format(
                        label)
                    self._fmt = re.sub(replace_re, text, self._fmt)

        self._colorized = True


# enable Logging
logging.handlers.ColorFormatter = ColorFormatter
