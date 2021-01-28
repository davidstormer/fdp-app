"""

Please DO NOT modify!

This file is imported and provides definitions for the main settings.py file.

Make any customizations in the main settings.py file.

Used to define default settings file to configure hosting in a Microsoft Azure environment.

"""
from .base_settings import *


# Specifies that FDP is configured for hosting in Microsoft Azure environment
USE_AZURE_SETTINGS = True


# External authentication mechanism.
EXT_AUTH = get_from_environment_var(environment_var='FDP_EXTERNAL_AUTHENTICATION', raise_exception=True)
EXT_AUTH = str(EXT_AUTH).lower()


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_from_environment_var(environment_var=ENV_VAR_FOR_FDP_SECRET_KEY, raise_exception=True)


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False


ALLOWED_HOSTS = [
    get_from_environment_var(environment_var='FDP_ALLOWED_HOST', raise_exception=True)
]


# external authentication such as through Azure Active Directory is supported
if EXT_AUTH == AAD_EXT_AUTH:
    INSTALLED_APPS.append(
        # Django Social Auth: https://python-social-auth-docs.readthedocs.io/en/latest/configuration/django.html
        'social_django'
    )
    TEMPLATE_CONTEXT_PROCESSORS.extend(
        [
            # Django Social Auth: https://python-social-auth-docs.readthedocs.io/en/latest/configuration/django.html
            'social_django.context_processors.backends',
            'social_django.context_processors.login_redirect'
        ]
    )
    CSP_FORM_ACTION = CSP_FORM_ACTION + ('https://www.office.com/', 'https://login.microsoftonline.com/',)
    AUTHENTICATION_BACKENDS.append('social_core.backends.azuread_tenant.AzureADTenantOAuth2')
    # Django Social Auth: https://python-social-auth-docs.readthedocs.io/en/latest/configuration/django.html
    # Enable JSONB field to store extracted extra data in PostgreSQL
    SOCIAL_AUTH_POSTGRES_JSONFIELD = True
    # Custom namespace for URL entries
    SOCIAL_AUTH_URL_NAMESPACE = 'social'
    # Authentication workflow is handled by an operations pipeline
    SOCIAL_AUTH_PIPELINE = (
        # Get the information we can about the user and return it in a simple
        # format to create the user instance later. On some cases the details are
        # already part of the auth response from the provider, but sometimes this
        # could hit a provider API.
        'social_core.pipeline.social_auth.social_details',
        # Get the social uid from whichever service we're authing thru. The uid is
        # the unique identifier of the given user in the provider.
        'social_core.pipeline.social_auth.social_uid',
        # Verifies that the current auth process is valid within the current
        # project, this is where emails and domains whitelists are applied (if
        # defined).
        'social_core.pipeline.social_auth.auth_allowed',
        # Checks if the current social-account is already associated in the site.
        'social_core.pipeline.social_auth.social_user',
        # Make up a username for this person, appends a random string at the end if
        # there's any collision.
        'social_core.pipeline.user.get_username',
        # Send a validation email to the user to verify its email address.
        # Disabled by default.
        # 'social_core.pipeline.mail.mail_validation',
        # Associates the current social details with another user account with
        # a similar email address. Disabled by default.
        # 'social_core.pipeline.social_auth.associate_by_email',
        # Create a user account if we haven't found one yet.
        # Disabled since it is replaced by customized method to set is_host
        # and only_external_auth properties.
        # 'social_core.pipeline.user.create_user',
        'fdp.pipeline.create_user',
        # Create the record that associates the social account with the user.
        'social_core.pipeline.social_auth.associate_user',
        # Populate the extra_data field in the social record with the values
        # specified by settings (and the default ones like access_token, etc).
        'social_core.pipeline.social_auth.load_extra_data',
        # Update the user record with any changed info from the auth service.
        'social_core.pipeline.user.user_details',
    )
    # Used to set search_fields property for Admin
    SOCIAL_AUTH_ADMIN_USER_SEARCH_FIELDS = ['email']
    # Azure Client ID
    SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_KEY = get_from_environment_var(
        environment_var='FDP_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_KEY', raise_exception=True
    )
    # Azure Tenant ID
    SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_TENANT_ID = get_from_environment_var(
        environment_var='FDP_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_TENANT_ID', raise_exception=True
    )
    # Allow the scope that is granted to the access token to be defined as default
    SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_IGNORE_DEFAULT_SCOPE = False
    # The auth process finishes with a redirect, by default it’s done to the value of SOCIAL_AUTH_LOGIN_REDIRECT_URL but
    # can be overridden with next GET argument. If this setting is True, this application will vary the domain of the
    # final URL and only redirect to it if it’s on the same domain.
    SOCIAL_AUTH_SANITIZE_REDIRECTS = True
    # On projects behind a reverse proxy that uses HTTPS, the redirect URIs can have the wrong schema (http:// instead
    # of https://) if the request lacks the appropriate headers, which might cause errors during the auth process. To
    # force HTTPS in the final URIs set this setting to True
    SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
    # A list of domain names to be white-listed. Any user with an email address on any of the allowed domains will login
    # successfully, otherwise AuthForbidden is raised.
    SOCIAL_AUTH_OAUTH2_WHITELISTED_DOMAINS = [
        get_from_environment_var(environment_var='FDP_SOCIAL_AUTH_OAUTH2_WHITELISTED_DOMAINS', raise_exception=True)
    ]
    # When disconnecting an account, it is recommended to trigger a token revoke action in the authentication provider,
    # that way we inform it that the token won’t be used anymore and can be disposed. By default the action is not
    # triggered because it’s not a common option on every provider, and tokens should be disposed automatically after a
    # short time.
    SOCIAL_AUTH_REVOKE_TOKENS_ON_DISCONNECT = True
    # De-authentication workflow is handled by an operations pipeline
    SOCIAL_AUTH_DISCONNECT_PIPELINE = (
        # Verifies that the social association can be disconnected from the current user (ensure that the user login
        # mechanism is not compromised by this disconnection).
        # 'social_core.pipeline.disconnect.allowed_to_disconnect',
        # Collects the social associations to disconnect.
        'social_core.pipeline.disconnect.get_entries',
        # Revoke any access_token when possible.
        'social_core.pipeline.disconnect.revoke_tokens',
        # Removes the social associations.
        'social_core.pipeline.disconnect.disconnect',
        # Forcibly logs out Django user
        'fdp.pipeline.logout_user',
    )


TEMPLATE_FIRST_DICT['OPTIONS'] = {'context_processors': TEMPLATE_CONTEXT_PROCESSORS}
TEMPLATES = [TEMPLATE_FIRST_DICT]


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': get_from_environment_var(environment_var=ENV_VAR_FOR_FDP_DATABASE_NAME, raise_exception=True),
    'USER': get_from_environment_var(environment_var=ENV_VAR_FOR_FDP_DATABASE_USER, raise_exception=True),
    'PASSWORD': get_from_environment_var(environment_var=ENV_VAR_FOR_FDP_DATABASE_PASSWORD, raise_exception=True),
    'HOST': get_from_environment_var(environment_var=ENV_VAR_FOR_FDP_DATABASE_HOST, raise_exception=True),
    'PORT': get_from_environment_var(environment_var=ENV_VAR_FOR_FDP_DATABASE_PORT, raise_exception=True)
}


# A URL-safe base64-encoded 32-byte key that is used by the Fernet symmetric encryption algorithm
# Used to encrypt and decrypt query string parameters
QUERYSTRING_PASSWORD = get_from_environment_var(
    environment_var=ENV_VAR_FOR_FDP_QUERYSTRING_PASSWORD, raise_exception=True
)


#: Azure Storage for Django: https://django-storages.readthedocs.io/en/latest/backends/azure.html
# Package-wide settings
# This setting is the Windows Azure Storage Account name, which in many cases is also the first part of the url for
# instance: http://azure_account_name.blob.core.windows.net/ would mean: AZURE_ACCOUNT_NAME = "azure_account_name"
AZURE_ACCOUNT_NAME = get_from_environment_var(environment_var='FDP_AZURE_STORAGE_ACCOUNT_NAME', raise_exception=True)
# This is the private key that gives Django access to the Windows Azure Account.
AZURE_ACCOUNT_KEY = get_from_environment_var(environment_var='FDP_AZURE_STORAGE_ACCOUNT_KEY', raise_exception=True)
# The custom domain to use. This can be set in the Azure Portal.
# For example, www.mydomain.com or mycdn.azureedge.net.
# It may contain a host:port when using the emulator (AZURE_EMULATED_MODE = True).
AZURE_CUSTOM_DOMAIN = '{a}.blob.core.windows.net'.format(a=AZURE_ACCOUNT_NAME)
# The file storage engine to use when collecting static files with the collectstatic management command.
# A ready-to-use instance of the storage backend defined in this setting can be found at
# django.contrib.staticfiles.storage.staticfiles_storage.
# Default: 'django.contrib.staticfiles.storage.StaticFilesStorage'
STATICFILES_STORAGE = 'fdp.backends.azure_blob_storage.StaticAzureStorage'
# This is where the static files uploaded through Django will be uploaded.
# The container must be already created, since the storage system will not attempt to create it.
AZURE_STATIC_CONTAINER = get_from_environment_var(environment_var='FDP_AZURE_STATIC_CONTAINER', raise_exception=True)
# Seconds before a URL expires, set to None to never expire it. Be aware the container must have public read
# permissions in order to access a URL without expiration date. Default is None
AZURE_STATIC_URL_EXPIRATION_SECS = get_from_environment_var(
    environment_var='FDP_AZURE_STATIC_EXPIRY', raise_exception=True
)
# URL to use when referring to static files located in STATIC_ROOT.
# Example: "/static/" or "http://static.example.com/"
# If not None, this will be used as the base path for asset definitions (the Media class) and the staticfiles
# app. It must end in a slash if set to a non-empty value.
# Default: None
STATIC_URL = 'https://{d}/{c}/'.format(d=AZURE_CUSTOM_DOMAIN, c=AZURE_STATIC_CONTAINER)
# The absolute path to the directory where collectstatic will collect static files for deployment.
# Example: "/var/www/example.com/static/"
# If the staticfiles contrib app is enabled (as in the default project template), the collectstatic management
# command will collect static files into this directory. See the how-to on managing static files for more
# details about usage.
# Default: None
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# This setting defines the additional locations the staticfiles app will traverse if the FileSystemFinder finder
# is enabled, e.g. if you use the collectstatic or findstatic management command or use the static file serving
# view.
# This should be set to a list of strings that contain full paths to your additional files directory(ies).
# Default: [] (Empty list)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, AZURE_ACCOUNT_NAME, 'static')
]

# Default file storage class to be used for any file-related operations that don’t specify a particular storage
# system. See Managing files.
# Default: 'django.core.files.storage.FileSystemStorage'
DEFAULT_FILE_STORAGE = 'fdp.backends.azure_blob_storage.MediaAzureStorage'
# This is where the media files uploaded through Django will be uploaded.
# The container must be already created, since the storage system will not attempt to create it.
AZURE_MEDIA_CONTAINER = get_from_environment_var(environment_var='FDP_AZURE_MEDIA_CONTAINER', raise_exception=True)
# URL that handles the media served from MEDIA_ROOT, used for managing stored files. It must end in a slash if
# set to a non-empty value. You will need to configure these files to be served in both development and
# production environments.
# If you want to use {{ MEDIA_URL }} in your templates, add 'django.template.context_processors.media' in the
# 'context_processors' option of TEMPLATES.
# Default: '' (Empty string)
MEDIA_URL = 'https://{d}/{c}/'.format(d=AZURE_CUSTOM_DOMAIN, c=AZURE_MEDIA_CONTAINER)
# Seconds before a URL expires, set to None to never expire it. Be aware the container must have public read
# permissions in order to access a URL without expiration date. Default is None
AZURE_MEDIA_URL_EXPIRATION_SECS = get_from_environment_var(
    environment_var='FDP_AZURE_MEDIA_EXPIRY', raise_exception=True
)


# This is where the files uploaded through Django will be uploaded.
# The container must be already created, since the storage system will not attempt to create it.
# AZURE_CONTAINER = None
# Set a secure connection (HTTPS), otherwise it makes an insecure connection (HTTP). Default is True
# AZURE_SSL = True
# Number of connections to make when uploading a single file. Default is 2
# AZURE_UPLOAD_MAX_CONN = 2
# Global connection timeout in seconds. Default is 20
# AZURE_CONNECTION_TIMEOUT_SECS = 20
# Maximum memory used by a downloaded file before dumping it to disk. Unit is in bytes. Default is 2MB
# AZURE_BLOB_MAX_MEMORY_SIZE = 2*1024*1024
# Seconds before a URL expires, set to None to never expire it. Be aware the container must have public read
# permissions in order to access a URL without expiration date. Default is None
# AZURE_URL_EXPIRATION_SECS = None
# Overwrite an existing file when it has the same name as the file being uploaded. Otherwise, rename it.
# Default is False
# AZURE_OVERWRITE_FILES = False
# Default location for the uploaded files. This is a path that gets prepended to every file name.
# AZURE_LOCATION = None
# Whether to use the emulator (i.e Azurite). Defaults to False.
# AZURE_EMULATED_MODE = False
# The host base component of the url, minus the account name. Defaults to Azure (core.windows.net).
# Override this to use the China cloud (core.chinacloudapi.cn).
# AZURE_ENDPOINT_SUFFIX = 'core.windows.net'
# If specified, this will override all other parameters.
# See http://azure.microsoft.com/en-us/documentation/articles/storage-configure-connection-string/ for the
# connection string format.
# AZURE_CONNECTION_STRING = None
# This is similar to AZURE_CONNECTION_STRING, but it’s used when generating the file’s URL. A custom domain or
# CDN may be specified here instead of within AZURE_CONNECTION_STRING. Defaults to AZURE_CONNECTION_STRING’s value.
# AZURE_CUSTOM_CONNECTION_STRING = AZURE_CONNECTION_STRING
# A token credential used to authenticate HTTPS requests. The token value should be updated before its expiration.
# AZURE_TOKEN_CREDENTIAL = None
# A variable to set the Cache-Control HTTP response header.
# E.g. AZURE_CACHE_CONTROL = "public,max-age=31536000,immutable"
# AZURE_CACHE_CONTROL = None
# Use this to set content settings on all objects. To set these on a per-object basis, subclass the backend and
# override AzureStorage.get_object_parameters.
# This is a Python dict and the possible parameters are: content_type, content_encoding, content_language,
# content_disposition, cache_control, and content_md5.
# AZURE_OBJECT_PARAMETERS = None
