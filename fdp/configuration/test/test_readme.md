# Writing and running tests for the FDP system

## Overview

The FDP system has predefined configuration settings that make it compatible with different hosting environments. These settings produce significant differences in how the system works, and even in the Python packages that are assumed to be installed.

To reflect this high degree of configurability, tests are designed to be compatible with particular predefined configuration settings.


## Writing tests

Each test class inherits from the `inheritable.models.AbstractTestCase` class.

If a class implements its own `setUp` method, it first makes a call its parents' `setUp` method:


    def setUp(self):
        """ ... """
        # skip setup and tests unless configuration is compatible
        super().setUp()
        ...


Each test method in each test class is marked with a decorator that can be found in `inheritable.models.py`, such as `@local_test_settings_required`. These decorators define the required configuration settings under which the test can be run.


## Running tests

Tests for a particular predefined configuration can be run by specifying the corresponding settings file found in `fdp.configuration.test`.

For example, the majority of the tests can be run with the local development environment configured: `python manage.py test --settings=fdp.configuration.test.test_local_settings`

Tests intended for the Microsoft Azure configuration with both Azure Active Directory and the default Django authentication backends supported, can be run with: `python manage.py test --settings=fdp.configuration.test.test_azure_settings`

Finally, tests intended for the Microsoft Azure configuration with only the Azure Active Directory authentication backend supported, can be run with: `python manage.py test --settings=fdp.configuration.test.test_azure_only_settings`

For more information on writing and running tests in Django, see: [https://docs.djangoproject.com/en/3.2/topics/testing/overview/](https://docs.djangoproject.com/en/3.2/topics/testing/overview/)
