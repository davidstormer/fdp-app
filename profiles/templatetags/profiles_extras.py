from django import template


register = template.Library()


@register.filter
def identifier_values(identifiers: list) -> str:
    """Returns a concatenated string of the identifier values from a list of identifier objects
    """
    if identifiers:
        identifiers_values = []
        for identifier in identifiers:
            identifiers_values.append(identifier.identifier)
        return ', '.join(identifiers_values)
    else:
        return ''

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
