#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-

'''Qubes logging routines.

See also: :py:attr:`qubes.vm.qubesvm.QubesVM.logger`

'''

import os
import re
import copy
import collections
import logging.config
import json

# Logging configuration file
try:
    import yaml
    from yaml.parser import ParserError
    from yaml.reader import ReaderError
    CONFIG_FILENAME = os.path.join(os.path.dirname(__file__), 'log.yaml')
except ImportError:
    CONFIG_FILENAME = os.path.join(os.path.dirname(__file__), 'log.json')

# Logging filename
LOG_FILENAME = '/var/log/qubes/qubes.log'


CONFIG = {
    'LOGFILE': LOG_FILENAME,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '%(message)s'},
        'simple': {
            'format': '%(asctime)s - %(levelname)9s - %(message)s'},
        'info': {
            'format': '%(asctime)s%(levelname)9s: %(name)s:[%(processName)s %(module)s.%(funcName)s:%(lineno)d]: %(message)s'},
        'debug': {
            'format': '%(asctime)s%(levelname)9s: %(name)s:[%(processName)s %(module)s.%(funcName)s:%(lineno)d]: %(message)s'},
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
    '''Enable global logging.

    Uses a YAML/JSON configuration file to set any configuration details

    :param str config_filename: YAML/JSON logging configuration filename
    :param int level: Logging level.  IE: 20 or logging.INFO
    :param str env_key: Environment key containing configuration filename

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


def enable_debug(config_filename=CONFIG_FILENAME,
                 env_key='LOG_CONFIG_FILENAME'):
    '''Enable debug logging.

    Enable more messages and additional info to message format.

    Uses a YAML/JSON configuration file to use custom handlers and formatters

    :param str config_filename: YAML/JSON logging configuration filename
    :param str env_key: Environment key containing configuration filename

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


def get_vm_logger(vmname, config_filename=CONFIG_FILENAME,
                  env_key='LOG_CONFIG_FILENAME'):
    '''Initialize logging for particular VM name.

    Uses a YAML/JSON configuration file to use custom handlers and formatters

    :param str vmname: VM's name
    :param str config_filename: YAML/JSON logging configuration filename
    :param str env_key: Environment key containing configuration filename
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
    '''Parse YAML/JSON Configuration file.

    Parses YAML/JSON configuration file which is converted into a dictionary that
    can be used with the logging configuration to set up logging defaults

    If an environmental variable is set with the same name as contained within
    env_key, that value is used as the filename over-riding a filename value if
    it also exists.

    :param str filename: YAML/JSON logging configuration filename
    :param str env_key: Environment key containing configuration filename
    :rtype: :py:class:`dict`

    '''

    message_noload = 'Can not load logging configuration file, using defaults: {0}'
    message_wrongformat = 'Configuration file {0} does not seem to be in JSON or YAML format. Using defaults.'
    message_nofile = 'Can not find logging configuration file {0}. Using defaults.'

    # Use the configuration filename provided in environment if available
    if env_key:
        filename = os.getenv(env_key, filename)

    # Enable logging with values in logging configuration file
    if filename and os.path.exists(filename):
        extension = os.path.splitext(filename)[1][1:].lower()

        if extension in ['json']:
            try:
                with open(filename, 'r') as infile:
                    config = json.load(infile)
            except (IOError) as e:
                config = {'__ERROR__': message_noload.format(e)}

        elif extension in ['yml', 'yaml']:
            try:
                with open(filename, 'r') as infile:
                    config = yaml.load(infile.read())
            except (IOError, ParserError, ReaderError) as e:
                config = {'__ERROR__': message_noload.format(e)}

        else:
            config = {'__ERROR__': message_wrongformat.format(filename)}
    else:
        config = {'__ERROR__': message_nofile.format(filename)}

    if '__ERROR__' in config.keys():
        config.update(CONFIG)

    return config


def add_logger(name, config, level=logging.INFO, filename=LOG_FILENAME,
               handlers=None, propagate=False):
    '''Add Logger.

    Adds a new logger using custom handlers and formatters described within
    the config dictionary

    :param dict config: Dictionary containing logging configuration directives
    :param int level: Logging level to set logger at
    :param str filename: Path and filename of logger log
    :param list handlers: List if handlers (str) to include.
    :param boolean propagate: If True, log events will also propagate to other loggers
    :rtype: :py:class:`logging.Logger`

    '''

    if not handlers:
        handlers = ['info_file_handler']

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
    '''Get Formatter.

    Uses the config dictionary to create and return a formatter

    :param dict config: Dictionary containing logging configuration directives
    :param str formatter: Name of formatter. Uses data in config['formatters'][name] to configure formatter
    :rtype: :py:class:`logging.Formatter`

    '''

    config = copy.deepcopy(config)
    dict_configurator = logging.config.DictConfigurator({})

    formatter_dict = config.get('formatters', {}).get(formatter, {})
    try:
        formatter_ = dict_configurator.configure_formatter(formatter_dict)
    except (StandardError) as e:
        raise ValueError('Unable to configure '
                         'formatter %r: %s' % (formatter, e))
    return formatter_


def get_formatters(config):
    '''Get Formatters.

    Iterates though config['formatters'] and updates the dictionary with
    instances of formatters contained within.

    :param dict config: Dictionary containing logging configuration directives
    :rtype: dict

    '''
    #config = copy.deepcopy(config)
    dict_configurator = logging.config.DictConfigurator({})

    formatters = config.get('formatters', {})
    for name in formatters:
        try:
            formatters[name] = dict_configurator.configure_formatter(
                formatters[name])
        except (StandardError) as e:
            raise ValueError('Unable to configure '
                             'formatter %r: %s' % (name, e))
    return formatters


def get_handler(config, handler, **args):
    '''Get Handler.

    Uses the config dictionary to create and return a handler

    :param dict config: Dictionary containing logging configuration directives
    :param str handler: Name of handler. Uses data in config['handlers'][name] to configure handler
    :param args: Additional configuration arguments used to override data within config
    :rtype: :py:class:`logging.handler`

    '''

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
    except (StandardError) as e:
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
        except (StandardError) as e:
            raise ValueError('Unable to configure handler '
                             '%r: %s' % (handler, e))

    handler_dict.formatter = formatter
    return handler_dict


def get_handlers(config, handlers=None, **args):
    '''Get Handlers.

    Iterates though config['handlers'] and creates a list of logging.handlers instances

    :param dict config: Dictionary containing logging configuration directives
    :param list handlers: List if handlers (str) to include.
    :param args: Additional configuration arguments used to override data within config
    :returns: list of :py:class:`logging.handlers`
    :rtype: list

    '''

    if handlers is None:
        handlers = config.get('handlers', {}).keys()

    results = {}
    for name in sorted(handlers):
        results[name] = get_handler(config, name, **args)

    return results


def ansi_text(text, color=None, bold=False, faint=False,
              underline=False, inverse=False, strike_through=False):
    '''Wrap text in ANSI escape codes.

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
    '''Converts all dictionary keys to lowercase.

    :param dict dictionary: Dictionary to convert
    :returns: Modified dictionary containing all lowercase keys
    :rtype: dict

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
    '''Color logging.Formatter.

    | Adds ASCI color codes to the logging output stream.  Each stream can be
    | customized within the configuration file to allow different colors per
    | field and optionally color field the same color as the ``levelname``.

    Sample YAML configuration:

    .. CODE:: yaml

        formatters:
          info:
            (): logging.handlers.ColorFormatter
            format: 'INFO: %(asctime)s%(levelname)9s: %(name)s:[%(processName)s %(module)s.%(funcName)s:%(lineno)d]: %(message)s'
            colors:
              levelname:
                DEBUG:    {color: green}
                INFO:     {color: magenta}
                VERBOSE:  {color: blue}
                WARNING:  {color: yellow}
                ERROR:    {color: red}
                CRITICAL: {color: red, bold: True}
                message:  {}
              asctime:     {color: yellow}
              name:        {color: blue}
              processname: {color: white}
              module:      {color: cyan}
              funcName:    {color: black, inverse: True}
              lineno:      {color: red}
            dynamic_labels: [lineno,]

    | The ColorFormatter is defined within the ``formatters`` section of the
    | configuration file within a formatter definition such as 'info' shown above.

    | (): logging.handlers.ColorFormatter is required to allow logging configuration
    | to load the module

    | The fields that desire coloring are within the ``colors`` section.  Each field
    | can contain a dictionary of color options.  The valid options are

    | color: ``black``, ``red``, ``green``, ``yellow``, ``blue``, ``magenta``,
    | ``cyan``, ``white``, or ``None``
    | bold: True or ``False``
    | faint: True or ``False``
    | underline: True or ``False``
    | inverse: True or ``False``
    | strike_through: True or ``False``

    | The ``levelname`` has a subsection that contains color codes for each logging
    | level.  The ``levelname`` field will then be colored then based on the level
    | logged which provides color indication per level.

    | Any other field name contained within the ``levelname`` section or listed
    | within the dynamic_labels list will be colored dynamically; that is they
    | will be colored the same color as the ``levelname``  field.

    '''

    def __init__(self, fmt=None, datefmt=None, colors=None,
                 dynamic_labels=None):
        '''Initialize the formatter with specified format strings.

        Initialize the formatter either with the specified format
        string, or a default as described above. Allow for specialized
        date formatting with the optional datefmt argument (if omitted,
        you get the ISO8601 format).

        '''

        if not colors:
            self.colors = {}
        else:
            self.colors = lower(colors)

        self.dynamic_labels = ['levelname', ]
        if dynamic_labels:
            self.dynamic_labels.extend(dynamic_labels)

        logging.Formatter.__init__(self, fmt=fmt, datefmt=datefmt)
        self._template = {'_master': copy.copy(self._fmt)}


    def format(self, record):
        '''Format the specified record as colorized text.

        The record's attribute dictionary is used as the operand to a
        string formatting operation which yields the returned string.
        Before formatting the dictionary, a couple of preparatory steps
        are carried out. The message attribute of the record is computed
        using LogRecord.getMessage(). If the formatting string uses the
        time (as determined by a call to usesTime(), formatTime() is
        called to format the event time. If there is exception information,
        it is formatted using formatException() and appended to the message.

        The format string is parsed and color codes are injected into it.  This
        only happens one time per formatter level, otherwise the record is cached.

        :param logging.LogRecord record: Logging log record
        :returns: Modified log record
        :rtype: :py:class:`logging.LogRecord`

        '''

        # Copy the original record so we don't break other handlers.
        record = copy.copy(record)

        if self.colors:
            # Caches by loglevel
            if logging.getLevelName(
                    record.levelno).lower() in self._template.keys():
                self._fmt = self._template[
                    logging.getLevelName(record.levelno).lower()]

            else:
                # Make sure message and asctime record fields are available
                # to color parser
                record.message = record.getMessage()
                if self.usesTime():
                    record.asctime = self.formatTime(record, self.datefmt)

                # Colorize existing 'template' once to reduce calls in colorizing
                # with the exception of fields that are dynamically colored
                self.colorize(record)
                self._template[
                    logging.getLevelName(record.levelno).lower()] = copy.copy(
                    self._fmt)

        return logging.Formatter.format(self, record)

    def colorize(self, record):
        '''Colorize.

        The log record is used to iterate though the available log fields and is
        compared against the color dictionary contained within the
        formatters.<formatter name> section within the configuration file.

        If a field exists in the colors section, then the format template
        is searched for the field and color codes are applied directly to the
        template.

        :param logging.LogRecord record: Logging log record

        '''

        for label in record.__dict__:

            if label not in self.colors.keys(
            ) and label not in self.dynamic_labels:
                # Add label to dynamic list if its color codes in levelname dict
                # This allows coloring the label same color as level color
                if label in self.colors.get('levelname', {}).keys():
                    self.dynamic_labels.append(label)

                # Label is not colorized
                else:
                    continue

            search_re = r'^.*(?P<label>%[(]\s*?{0}\s*[)].*?[diouxXeEfFgGcrs%]).*'.format(
                label)
            match = re.match(search_re, self._fmt)

            if not match:
                continue

            if label in self.dynamic_labels:
                colors = self.colors.get('levelname', {}).get(
                    logging.getLevelName(record.levelno).lower(), {})
            else:
                colors = self.colors.get(label, {})

            if colors:
                text = match.group('label')
                text = ansi_text(text=text, **colors)
                replace_re = r'(%[(]\s*?{0}\s*[)].*?[diouxXeEfFgGcrs%])'.format(
                    label)
                self._fmt = re.sub(replace_re, text, self._fmt)


# Enable ColorFormatter handler
logging.handlers.ColorFormatter = ColorFormatter
