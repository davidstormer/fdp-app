"""

Please DO NOT modify!

This file is used in automated tests, i.e. python manage.py test --settings=fdp.configuration.test.test_local_settings

Used to define settings to simulate a Microsoft Azure environment for automated tests.

"""
#: Automated tests are only intended to be run in a local development environment.
from fdp.configuration.local.local_settings import *
from fdp.configuration.test.loggers import LOGGING

