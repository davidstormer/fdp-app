"""

Please DO NOT modify!

This file is used in automated tests, i.e. python manage.py test --settings=fdp.configuration.test.test_azure_settings

Used to define settings to simulate a Microsoft Azure environment for automated tests.

"""
from fdp.configuration.abstract.constants import CONST_AZURE_AUTH_BACKEND, CONST_AZURE_OTP_MIDDLEWARE, \
    CONST_AZURE_AUTH_APP, CONST_AZURE_TEMPLATE_CONTEXT_PROCESSORS

#: Automated tests are only intended to be run in a local development environment.
from fdp.configuration.local.local_settings import *
from fdp.configuration.test.loggers import LOGGING

USE_LOCAL_SETTINGS = False


USE_TEST_AZURE_SETTINGS = True


USE_AZURE_SETTINGS = True


EXT_AUTH = AAD_EXT_AUTH


MIDDLEWARE = FIRST_MIDDLEWARE + CONST_AZURE_OTP_MIDDLEWARE + LAST_MIDDLEWARE


INSTALLED_APPS.append(CONST_AZURE_AUTH_APP)


TEMPLATE_CONTEXT_PROCESSORS.extend(CONST_AZURE_TEMPLATE_CONTEXT_PROCESSORS)
TEMPLATE_FIRST_DICT['OPTIONS'] = {'context_processors': TEMPLATE_CONTEXT_PROCESSORS}
TEMPLATES = [TEMPLATE_FIRST_DICT]


RECAPTCHA_PUBLIC_KEY = ''


RECAPTCHA_PRIVATE_KEY = ''


AUTHENTICATION_BACKENDS.append(CONST_AZURE_AUTH_BACKEND)
