from django import template
from inheritable.models import AbstractConfiguration


register = template.Library()


@register.simple_tag
def is_azure_active_directory_configured():
    """ Checks whether support for Azure Active Directory authentication is correctly configured.

    :return: True if support for Azure Active Directory authentication is correctly configured, false otherwise.
    """
    return AbstractConfiguration.can_do_azure_active_directory()


@register.simple_tag
def is_password_reset_configured():
    """ Checks whether the password reset functionality is correctly configured, e.g. the required reCAPTCHA and
    email settings are specified.

    :return: True if the password reset functionality is correctly configured, false otherwise.
    """
    return AbstractConfiguration.can_do_password_reset()
