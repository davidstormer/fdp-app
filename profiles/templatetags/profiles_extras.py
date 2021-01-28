from django import template
from django.conf import settings


register = template.Library()


@register.filter
def get_value(dictionary, key):
    """ Retrieve a value from a dictionary given a particular key.

    :param dictionary: Dictionary from which to retrieve value.
    :param key: Key for which to retrieve value.
    :return: Value retrieved from the dictionary with the key.
    """
    return dictionary.get(key)


@register.filter
def get_item(list_obj, index):
    """ Retrieve an item from a list given a particular index.

    :param list_obj: List from which to retrieve item.
    :param index: Index for which to retrieve item.
    :return: Item retrieved from the list with the index.
    """
    return list_obj[index]


@register.simple_tag
def get_font_awesome_src():
    """ Retrieves the full URL that will be placed into the SRC attribute for the SCRIPT element to load the Font
    Awesome icon set.

    :return: URL that will be placed into the SRC attirbute for the SCRIPT element.
    """
    return settings.FONT_AWESOME_SRC
