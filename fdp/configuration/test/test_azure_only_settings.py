"""

Please DO NOT modify!

This file is used in automated tests,
i.e. python manage.py test --settings=fdp.configuration.test.test_azure_only_settings

Used to define settings to simulate a Microsoft Azure environment for automated tests.

"""
from fdp.configuration.abstract.constants import CONST_AZURE_AUTH_BACKEND, CONST_AZURE_OTP_MIDDLEWARE, \
    CONST_AZURE_AUTH_APP, CONST_AZURE_TEMPLATE_CONTEXT_PROCESSORS

#: Automated tests are only intended to be run in a local development environment.
#: These automated tests are based on the test configuration for the Microsoft Azure environment.
from .test_azure_settings import *
#: Use configuration that is intended to restrict to only Microsoft Azure authentication.
from fdp.configuration.azure.azure_only_settings import *
