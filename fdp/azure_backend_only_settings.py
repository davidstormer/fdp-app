"""

Please DO NOT modify!

This file is imported and provides definitions for the main settings.py file.

Make any customizations in the main settings.py file.

Used to enforce user authentication only through the Microsoft Azure Active Directory backend.

"""
from .constants import CONST_AXES_AUTH_BACKEND, CONST_AZURE_AUTH_BACKEND
from django.urls import reverse_lazy


#: Support only the Azure Active Directory user authentication backend
USE_ONLY_AZURE_AUTH = True


#: Always redirect the login URL to the Azure Active Directory login
LOGIN_URL = reverse_lazy('social:begin', args=['azuread-tenant-oauth2'])


#: Disable Django's default database-driven user authentication
AUTHENTICATION_BACKENDS = [
    # Django Axes: https://django-axes.readthedocs.io/en/latest/
    CONST_AXES_AUTH_BACKEND,
    # Azure Active Directory: https://python-social-auth.readthedocs.io/en/latest/backends/azuread.html
    CONST_AZURE_AUTH_BACKEND
]
