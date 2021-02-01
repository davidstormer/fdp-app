"""

Please DO NOT modify!

This file is imported and provides definitions for the main settings.py file.

Make any customizations in the main settings.py file.

Used to define default settings file to configure hosting in a local development environment.

Not intended for use in a production environment.

"""
from .base_settings import *


# Specifies that FDP is configured for hosting in a local development environment
USE_LOCAL_SETTINGS = True


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_from_environment_var_or_conf_file(
    environment_var=ENV_VAR_FOR_FDP_SECRET_KEY, conf_file='fdp_sk.conf', default_val=''
)


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True


ALLOWED_HOSTS = ['127.0.0.1']


TEMPLATE_FIRST_DICT['OPTIONS'] = {'context_processors': TEMPLATE_CONTEXT_PROCESSORS}
TEMPLATES = [TEMPLATE_FIRST_DICT]


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': get_from_environment_var_or_conf_file(
        environment_var=ENV_VAR_FOR_FDP_DATABASE_NAME, conf_file='fdp_database_name.conf', default_val='fdp'
    ),
    'USER': get_from_environment_var_or_conf_file(
        environment_var=ENV_VAR_FOR_FDP_DATABASE_USER, conf_file='fdp_database_user.conf', default_val='django_fdp'
    ),
    'PASSWORD': get_from_environment_var_or_conf_file(
        environment_var=ENV_VAR_FOR_FDP_DATABASE_PASSWORD, conf_file='fdp_ps.conf', default_val=''
    ),
    'HOST': get_from_environment_var_or_conf_file(
        environment_var=ENV_VAR_FOR_FDP_DATABASE_HOST, conf_file='fdp_database_host.conf', default_val='localhost'
    ),
    'PORT': get_from_environment_var_or_conf_file(
        environment_var=ENV_VAR_FOR_FDP_DATABASE_PORT, conf_file='fdp_database_port.conf', default_val='5432'
    )
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/
STATIC_URL = '/static/'
# static files copied to STATIC_ROOT by $ python manage.py collectstatic command
STATIC_ROOT = ONE_UP_BASE_DIR / 'static'


# Media files (user uploaded files for attachments, etc.)
# URL that handles the media served from MEDIA_ROOT, used for managing stored files. It must end in a slash if set
# to a non-empty value. You will need to configure these files to be served in both development and production
# environments.
# If you want to use {{ MEDIA_URL }} in your templates, add 'django.template.context_processors.media' in the
# 'context_processors' option of TEMPLATES.
# Default: '' (Empty string)
MEDIA_URL = '/media/'
# root folder into which media files are uploaded by users
MEDIA_ROOT = ONE_UP_BASE_DIR / 'media'


# Secure session cookies can be HTTPS only
SESSION_COOKIE_SECURE = False

# Secure CSRF cookies can be HTTPS only
CSRF_COOKIE_SECURE = False

# Always redirect to HTTPS
SECURE_SSL_REDIRECT = False

# Http Strict Transport Security instructs browser to refuse unsecured HTTP connections (only HTTPS allowed)
# 86400 = 1 day
# 10368000 = 120 days
# 31536000 = 1 year
# Set HSTS header for x seconds
SECURE_HSTS_SECONDS = 0
# Add includeSubDomains directive to HSTS header
SECURE_HSTS_INCLUDE_SUBDOMAINS = False


# A URL-safe base64-encoded 32-byte key that is used by the Fernet symmetric encryption algorithm
# Used to encrypt and decrypt query string parameters
QUERYSTRING_PASSWORD = get_from_environment_var_or_conf_file(
    environment_var=ENV_VAR_FOR_FDP_QUERYSTRING_PASSWORD, conf_file='fdp_qs.conf', default_val=''
)


# Google reCAPTCHA using Django-reCAPTCHA package
# See: https://github.com/praekelt/django-recaptcha
# See: https://www.google.com/recaptcha
# Google provides test keys which are set as the default for RECAPTCHA_PUBLIC_KEY and RECAPTCHA_PRIVATE_KEY.
# These cannot be used in production since they always validate to true and a warning will be shown on the reCAPTCHA.
# To bypass the security check that prevents the test keys from being used unknowingly
# add SILENCED_SYSTEM_CHECKS = [..., 'captcha.recaptcha_test_key_error', ...] to your settings
SILENCED_SYSTEM_CHECKS = ['captcha.recaptcha_test_key_error']
