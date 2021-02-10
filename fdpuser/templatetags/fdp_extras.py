from django import template
from django.apps import apps
from inheritable.models import AbstractConfiguration


register = template.Library()


@register.simple_tag
def is_extra_auth_installed():
    """ Checks whether the additional authentication system is connected, e.g. whether users can login through Azure
    Active Directory.

    :return: True if additional authentication system is connected and enabled, false otherwise.
    """
    return apps.is_installed('social_django')


@register.simple_tag
def is_password_reset_configured():
    """ Checks whether the password reset functionality is correctly configured, e.g. the required reCAPTCHA and
    email settings are specified.

    :return: True if the password reset functionality is correctly configured, false otherwise.
    """
    return AbstractConfiguration.can_do_password_reset()
