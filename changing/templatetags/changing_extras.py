import os.path

from django import template
from django.conf import settings
from django.forms import formsets
from inheritable.forms import AbstractWizardModelForm


register = template.Library()


@register.filter
def hide_in_html(field):
    """ Retrieve whether a field should be hidden in the HTML template when it is rendered.

    :param field: Field to check.
    :return: True if field should be hidden when it is rendered, false otherwise.
    """
    return getattr(field, AbstractWizardModelForm.hide_param, False)


@register.filter
def is_management_field(field):
    """ Checks whether field is used for form management and should be hidden in the HTML template when it is rendered.

    :param field: Field to check.
    :return: True if field is used for form management and so should be hidden when it is rendered, false otherwise.
    """
    return field.name in [formsets.DELETION_FIELD_NAME]


@register.filter
def get_value(dictionary, key):
    """ Retrieve a value from a dictionary given a particular key.

    :param dictionary: Dictionary from which to retrieve value.
    :param key: Key for which to retrieve value.
    :return: Value retrieved from the dictionary with the key.
    """
    return dictionary.get(key)


@register.filter
def basename(file_field):
    return os.path.basename(str(file_field))
