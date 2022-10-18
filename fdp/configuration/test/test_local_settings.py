"""

Please DO NOT modify!

This file is used in automated tests, i.e. python manage.py test --settings=fdp.configuration.test.test_local_settings

Used to define settings to simulate a Microsoft Azure environment for automated tests.

"""
#: Automated tests are only intended to be run in a local development environment.
from fdp.configuration.local.local_settings import *
from fdp.configuration.test.loggers import LOGGING


#: Enable by default, the EULA splash page, so that all relevant URLs are available for testing.
FDP_EULA_SPLASH_ENABLE = True

# Change password hashing algorithm to MD5 for faster running tests
# https://docs.djangoproject.com/en/3.2/topics/testing/overview/#speeding-up-the-tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
