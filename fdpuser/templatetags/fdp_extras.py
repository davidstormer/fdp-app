from django import template
from django.apps import apps


register = template.Library()


@register.simple_tag
def is_extra_auth_installed():
    """ Checks whether the additional authentication system is connected, e.g. whether users can login through Azure
    Active Directory.

    :return: True if additional authentication system is connected and enabled, false otherwise.
    """
    return apps.is_installed('social_django')
