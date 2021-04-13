"""
Django settings for Full Disclosure project.

Generated by 'django-admin startproject' using Django 3+.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""


#: To configure hosting in a local development environment, remove the comment from the below import statement.
#: This should not be used in a production environment.
# from .configuration.local.local_settings import *
from .configuration.azure.azure_settings import *

#: To configure hosting in a Microsoft Azure environment, remove the comment from the below import statement.
# from .configuration.azure.azure_settings import *


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


#: To enable logging, remove the comments from the below assignments.
# FDP_ERR_LOGGING['handlers']['file']['filename'] = BASE_DIR / 'debug.log'
# LOGGING = FDP_ERR_LOGGING

# DEBUG SETTING
# Don't limit number of parameters in post/get requests
# https://docs.djangoproject.com/en/2.2/ref/settings/#data-upload-max-number-fields
# Resolves 400 error when submitting bulk change and clicking "Select all XYZ [objects]"
# https://stackoverflow.com/questions/55921865/django-admin-deleting-all-records-bad-request-400
DATA_UPLOAD_MAX_NUMBER_FIELDS = None
