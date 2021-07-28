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
        "azure": {
            "level": "DEBUG",
            "class": "opencensus.ext.azure.log_exporter.AzureLogHandler",
            "instrumentation_key": "618ff4ad-f5b2-4e93-a0d3-ab41e502dfd7",
         },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
         },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': '/tmp/fdp-app.log',
        },
    },
    "loggers": {
        "logger_name": {"handlers": ["azure", "console", "file"]},
    },
}

#: To allow files to be downloaded during a bulk import using the Django Data Wizard package, whitelist the
# starting portion of each URL. For example, to download files from either Air Tables or Google Drive:
# FDP_DJANGO_DATA_WIZARD_WHITELISTED_URLS = ['https://airtable.com/', 'https://drive.google.com/file/']
