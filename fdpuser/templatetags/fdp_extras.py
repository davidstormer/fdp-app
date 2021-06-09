from django import template
from django.contrib.auth import get_user_model
from inheritable.models import AbstractConfiguration, AbstractUrlValidator


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


@register.simple_tag
def is_django_2fa_skipped_for_azure():
    """ Checks whether the 2FA verification in Django can be skipped for users authenticated through Azure Active
    Directory.

    :return: True if 2FA verification in Django can be skipped for users authenticated through Azure Active Directory,
    false otherwise.
    """
    return AbstractConfiguration.skip_django_2fa_for_azure()


@register.simple_tag
def is_azure_authenticated(user):
    """ Checks whether a user is authenticated through Azure Active Directory.

    :param user: User whose authentication should be checked.
    :return: True if user is authenticated through Azure Active Directory, false otherwise.
    """
    user_model = get_user_model()
    return user_model.is_user_azure_authenticated(user=user)


@register.simple_tag
def azure_ad_provider():
    """ Retrieves the provider that is used by Django Social Auth package to allow users to authenticate through Azure
    Active Directory.

    :return: Provider used by Django Social Auth package.
    """
    return AbstractConfiguration.azure_active_directory_provider


@register.simple_tag
def get_abstract_url_validator_attr(attr_to_get):
    """ Retrieves an attribute from the AbstractUrlValidator class that is used to encapsulate constants and methods
    used to validate URLs.

    Used to standardize keys and variables when working with AJAX on the client-side.

    :param attr_to_get: Name of attribute to retrieve.
    :return: Value of attribute.
    """
    return getattr(AbstractUrlValidator, attr_to_get)
