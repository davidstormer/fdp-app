"""

Please DO NOT modify!

This file is imported and provides definitions for the various settings files.

Make any customizations in the main settings.py file.

Used to define constants that are referenced throughout the various settings files.

"""
#: Authentication backend for Django Axes package: https://django-axes.readthedocs.io/en/latest/
CONST_AXES_AUTH_BACKEND = 'axes.backends.AxesBackend'


#: Django's default database-driven authentication backend
CONST_DJANGO_AUTH_BACKEND = 'django.contrib.auth.backends.ModelBackend'


#: Middleware handling Django Two-Factor Authentication when hosting in a Microsoft Azure environment.
CONST_AZURE_OTP_MIDDLEWARE = ['fdp.middleware.azure_middleware.AzureOTPMiddleware']


#: Name of Django app to add into INSTALLED_APPS setting to support authentication through Azure Active Directory.
#: Django Social Auth: https://python-social-auth-docs.readthedocs.io/en/latest/configuration/django.html
CONST_AZURE_AUTH_APP = 'social_django'


#: Additional context processors to add into TEMPLATES setting to support authentication through Azure Active Directory.
#: Django Social Auth: https://python-social-auth-docs.readthedocs.io/en/latest/configuration/django.html
CONST_AZURE_TEMPLATE_CONTEXT_PROCESSORS = [
    'social_django.context_processors.backends',
    'social_django.context_processors.login_redirect'
]


#: Authentication backend for Azure Active Directory
#: See: https://python-social-auth.readthedocs.io/en/latest/backends/azuread.html
CONST_AZURE_AUTH_BACKEND = 'social_core.backends.azuread_tenant.AzureADTenantOAuth2'


#: Value for provider that will define a social authentication record linked to a user authenticated who is
#: through Azure Active Directory.
#: See: https://python-social-auth.readthedocs.io/en/latest/backends/azuread.html
CONST_AZURE_AD_PROVIDER = 'azuread-tenant-oauth2'
