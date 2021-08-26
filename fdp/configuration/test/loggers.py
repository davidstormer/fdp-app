"""Check the environment variable 'FDP_TESTS_LOGGING_VERBOSITY' for a logging level 0-2 and set LOGGING to a
corresponding logging configuration, befitting the level. Simply import the LOGGING variable from this module into your
configuration file to use the logging configuration.
"""
import os
import logging

_DEBUG_TESTS = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console_tests_only': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['tests_only'],
        },
        'console_all_sources': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }
    },
    'root': {
        'handlers': ['console_tests_only'],
        'level': 'DEBUG',
    },
    'formatters': {
        'verbose': {
            'format': '{name:18}: {message} {pathname}',
            'style': '{',
        },
    },
    'filters': {
        'tests_only': {
            '()': 'fdp.configuration.test.loggers._TestLogsOnly'
        }
    }
}
"""Use DEBUG_TESTS to show additional context debug messages from tests.py files while running tests. E.g. "Starting
person changing ..." This logger sets the level to DEBUG and filters messages to only show log messages coming 
from tests.py file (i.e. tests modules). Note that non-tests messages of level WARNING and above will still be 
printed to the console, per the default behavior of Python loggers with no explicit destination [1].
[1] https://docs.python.org/3/howto/logging.html#advanced-logging-tutorial
"""

_DEBUG_EVERYTHING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console_tests_only': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'console_all_sources': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }
    },
    'root': {
        'handlers': ['console_tests_only'],
        'level': 'DEBUG',
    },
    'formatters': {
        'verbose': {
            'format': '{name:18}: {message} {pathname}',
            'style': '{',
        },
    },
}
"""Use DEBUG_EVERYTHING to see all messages of level DEBUG and up coming from any module whatever. I.e. firehose mode.
"""


class _TestLogsOnly(logging.Filter):
    def filter(self, record) -> bool:
        return record.module == 'tests'


def _generate_tests_logging_config():
    """Return a logging configuration from a set of predefined options (above).
    If no option is given set the logger to None, which will have no effect when Django merges it with the Django
    default logging configuration. https://github.com/django/django/blob/main/django/utils/log.py
    """
    verbosity_levels = {
        None: None,  # Do nothing, use the existing logger
        '0': None,  # Do nothing, use the existing logger
        '1': _DEBUG_TESTS,
        '2': _DEBUG_EVERYTHING,
    }

    try:
        logging_config = verbosity_levels[os.environ.get('FDP_TESTS_LOGGING_VERBOSITY')]
    except KeyError:
        print(f"FDP_TESTS_LOGGING_VERBOSITY: '{os.environ.get('FDP_TESTS_LOGGING_VERBOSITY')}' option not "
              f"found. Falling back to default logging configuration.")
        logging_config = None

    return logging_config


LOGGING = _generate_tests_logging_config()
"""Import the LOGGING variable into your config file to get a logging configuration configured based on the level set in
the 'FDP_TESTS_LOGGING_VERBOSITY' environment variable. See docstring for this module for more information.
"""
