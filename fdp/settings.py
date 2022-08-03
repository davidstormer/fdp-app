"""
Django settings for Full Disclosure project.

Generated by 'django-admin startproject' using Django 3+.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
import sys


#: To configure hosting in a local development environment, remove the comment from the below import statement.
#: This should not be used in a production environment.
# from .configuration.local.local_settings import *


#: To configure hosting in a Microsoft Azure environment, remove the comment from the below import statement.
from .configuration.azure.azure_settings import *

FDP_EULA_SPLASH_ENABLE = True

DATA_WIZARD_STATUS_CHECK_SECONDS = 3

#: To enforce user authentication only through the Azure Active Directory backend, remove the comment from the below
# import statement.
# from .configuration.azure.azure_only_settings import *


# Name of Python file containing class that defines person profile searches.
FDP_PERSON_PROFILE_SEARCH_FILE = 'def_person'
# Name of class inheriting from AbstractProfileSearch that defines person profile searches.
FDP_PERSON_PROFILE_SEARCH_CLASS = 'PersonProfileSearch'
# Name of Python file containing class that defines grouping profile searches.
FDP_GROUPING_PROFILE_SEARCH_FILE = 'def_grouping'
# Name of class inheriting from AbstractProfileSearch that defines grouping profile searches.
FDP_GROUPING_PROFILE_SEARCH_CLASS = 'GroupingProfileSearch'
# Name of Python file containing class that defines person changing searches.
FDP_PERSON_CHANGING_SEARCH_FILE = 'def_person'
# Name of class inheriting from AbstractChangingSearch that defines person changing searches.
FDP_PERSON_CHANGING_SEARCH_CLASS = 'PersonChangingSearch'
# Name of Python file containing class that defines incident changing searches.
FDP_INCIDENT_CHANGING_SEARCH_FILE = 'def_incident'
# Name of class inheriting from AbstractChangingSearch that defines person changing searches.
FDP_INCIDENT_CHANGING_SEARCH_CLASS = 'IncidentChangingSearch'
# Name of Python file containing class that defines content changing searches.
FDP_CONTENT_CHANGING_SEARCH_FILE = 'def_content'
# Name of class inheriting from AbstractChangingSearch that defines content changing searches.
FDP_CONTENT_CHANGING_SEARCH_CLASS = 'ContentChangingSearch'
# Name of Python file containing class that defines grouping changing searches.
FDP_CONTENT_GROUPING_SEARCH_FILE = 'def_grouping'
# Name of class inheriting from AbstractChangingSearch that defines content changing searches.
FDP_CONTENT_GROUPING_SEARCH_CLASS = 'GroupingChangingSearch'

# Send log messages to Azure Monitor
# Uncomment the below code and paste in
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    "handlers": {
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
         },
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': '/tmp/fdp-app.log',
        },
    },
    'root': {
        'handlers': ["console", "file"],
        'level': 'WARNING',
    },
}

#: To allow files to be downloaded during a bulk import using the Django Data Wizard package, whitelist the
# starting portion of each URL. For example, to download files from either Air Tables or Google Drive:
# FDP_DJANGO_DATA_WIZARD_WHITELISTED_URLS = ['https://airtable.com/', 'https://drive.google.com/file/']


#: To customize the options that are listed on the federated login page, remove the comments from the below assignment.
# If no options are listed below, the federated login page will be skipped, and the user will be automatically
# redirected to the primary login page.
FEDERATED_LOGIN_OPTIONS = [
    {
        'label': 'Sign in with FDP',
        'url_pattern_name': 'two_factor:login',
        'url_pattern_args': [],
        'css': {'background-color': '#417690', 'color': '#FFF'},
        'css_hover': {'color': '#f5dd5d'}
    },
    {
        'label': 'Sign in with Azure Active Directory',
        'url_pattern_name': 'social:begin',
        'url_pattern_args': ['inheritable.models.AbstractConfiguration.azure_active_directory_provider'],
        'css': {'background-color': '#417690', 'color': '#FFF'},
        'css_hover': {'color': '#f5dd5d'}
    }
]
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

LEGACY_OFFICER_SEARCH_ENABLE = True
