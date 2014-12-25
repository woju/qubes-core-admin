#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-

# autopep8 --ignore E309 -a -i

'''Qubes logging routines

See also: :py:attr:`qubes.vm.qubesvm.QubesVM.logger`
'''

import collections
import copy
import logging.config
import os
import re

import yaml
from yaml.parser import ParserError


# XXX: - I can change this to json or ini if we don't want to use yaml lib
#      - I will provide examples of all formats to show differences in
#        readability
#FORMAT_CONSOLE = '%(message)s'
#FORMAT_LOG = '%(asctime)s%(levelname)8s: %(module)s.%(funcName)s: %(message)s'
#FORMAT_DEBUG = '%(asctime)s %(levelname)s:[%(processName)s %(module)s.%(funcName)s:%(lineno)d] %(name)s: %(message)s'
#LOGPATH = '/var/log/qubes'
#LOGFILE = os.path.join(LOGPATH, 'qubes.log')

# Keep incase we have a problem loading configuration file so logs will
# still work in basic mode
LOGPATH = '/var/log/qubes'
LOGFILE = os.path.join(LOGPATH, 'qubes.log')

#FORMATTER_CONSOLE = logging.Formatter(FORMAT_CONSOLE)
#FORMATTER_LOG = logging.Formatter(FORMAT_LOG)
#FORMATTER_DEBUG = logging.Formatter(FORMAT_DEBUG)

# Logging in configuration file so it can be changed easily without
# touching code
LOGGING_CONFIGURATION = os.path.join(os.path.dirname(__file__), 'log.yaml')

ANSI_COLORS = {
    ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
    [i]: i for i in range(8)
}


def ansi_text(text, color=None, bold=False, faint=False,
              underline=False, inverse=False, strike_through=False):
    """
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
    """

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


def setup(log_path=LOGGING_CONFIGURATION, log_level=logging.INFO,
          env_key='LOG_CFG'):
    '''Setup logging configuration

    LOG_CFG=logging.yaml python

    '''
    if logging.root.handlers:
        return

    path = log_path
    value = os.getenv(env_key, None)

    if value:
        path = value
    if os.path.exists(path):
        try:
            with open(path, 'rt') as infile:
                config = yaml.load(infile.read())
            logging.config.dictConfig(config)
        except (IOError, ParserError) as e:
            logging.basicConfig(filename=LOGFILE, level=log_level,
                                encoding='utf-8')
            logging.error('Can not load logging configuration file: ',
                          exc_info=True)
    else:
        logging.basicConfig(
            filename=LOGFILE,
            level=log_level,
            encoding='utf-8')
        logging.error(
            'Can not load logging configuration file: {0}'.format(path))


def enable():
    '''Enable global logging

    Use :py:mod:`logging` module from standard library to log messages.

    >>> import qubes.log
    >>> qubes.log.enable()          # doctest: +SKIP
    >>> import logging
    >>> logging.warning('Foobar')   # doctest: +SKIP
    '''
    setup()

    # if logging.root.handlers:
    # return

    # handler_console = logging.StreamHandler(sys.stderr)
    # handler_console.setFormatter(FORMATTER_CONSOLE)
    # logging.root.addHandler(handler_console)

    # handler_log = logging.FileHandler(LOGFILE, 'a', encoding='utf-8')
    # handler_log.setFormatter(FORMATTER_LOG)
    # logging.root.addHandler(handler_log)

    # logging.root.setLevel(logging.INFO)


def enable_debug():
    '''Enable debug logging

    Enable more messages and additional info to message format.
    '''
    setup()

    logging.root.setLevel(logging.DEBUG)

    for handler in logging.root.handlers:
        handler.setFormatter(FORMATTER_DEBUG)


def get_vm_logger(vmname):
    '''Initialize logging for particular VM name

    :param str vmname: VM's name
    :rtype: :py:class:`logging.Logger`
    '''

    logger = logging.getLogger('vm.' + vmname)
    handler = logging.FileHandler(os.path.join(LOGPATH, 'vm', vmname + '.log'))
    handler.setFormatter(FORMATTER_LOG)
    logger.addHandler(handler)

    return logger

# enable Logging
logging.handlers.ColorFormatter = ColorFormatter
setup()
