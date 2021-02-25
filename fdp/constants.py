"""

Please DO NOT modify!

This file is imported and provides definitions for the various settings files.

Make any customizations in the main settings.py file.

Used to define constants that are referenced throughout the various settings files.

"""
#: Authentication backend for Django Axes package: https://django-axes.readthedocs.io/en/latest/
CONST_AXES_AUTH_BACKEND = 'axes.backends.AxesBackend'


#: Authentication backend for Azure Active Directory
#: See: https://python-social-auth.readthedocs.io/en/latest/backends/azuread.html
CONST_AZURE_AUTH_BACKEND = 'social_core.backends.azuread_tenant.AzureADTenantOAuth2'
