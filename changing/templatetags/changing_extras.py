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


@register.simple_tag
def get_font_awesome_src():
    """ Retrieves the full URL that will be placed into the SRC attribute for the SCRIPT element to load the Font
    Awesome icon set.

    :return: URL that will be placed into the SRC attirbute for the SCRIPT element.
    """
    return settings.FONT_AWESOME_SRC
