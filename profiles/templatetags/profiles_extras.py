from django import template
from django.utils.safestring import mark_safe
from django import template
from django.template import Template, Context
from core.models import PersonContact
from supporting.models import State
from profiles.common import sanitize_custom_text_html

register = template.Library()


@register.filter
def contact_address_in_one_line(contact: PersonContact) -> str:
    """Takes a PersonContact, returns an address formatted to fit on a single line.
    """

    # Concatenate state and zip together with no comma
    # c.f.: https://courses.lumenlearning.com/englishforbusiness/chapter/2-1-commas/
    if contact.state and contact.zip_code:
        state_zip = f"{contact.state.name} {contact.zip_code}"
    elif contact.state:
        state_zip = f"{contact.state.name}"
    elif contact.zip_code:
        state_zip = f"{contact.zip_code}"
    else:
        state_zip = ''
    address_component_values = [
        contact.address,
        contact.city,
        state_zip
    ]
    address_output = ''
    # Concatenate and comma delimit the address components
    for i, field_value in enumerate(address_component_values):
        # Prepend comma
        # If it's the first element, don't prepend a comma or space
        if len(address_output) > 0:
            # If there's no value, don't prepend a comma or space
            if field_value:
                address_output += ', '
        # Concatenate field value
        if field_value:
            address_output += field_value
    return address_output


@register.filter
def parenthesize(text: any) -> str:
    """If a value contains anything, wrap it in with parenthesise, and prepend with one space. If not, just pass it on.
    """
    if text:
        template = Template(f"&nbsp;({text})")
        return template.render(Context({'text': text}))
    else:
        return text


@register.filter
def sanitize_html(untrusted_html: str) -> str:
    """Sanitize user submitted text, allowing short-list of html tags for formatting.
    """
    return sanitize_custom_text_html(untrusted_html)


@register.simple_tag(takes_context=True)
def link_to_others(context, other_person) -> str:
    """
    If it's me, don't make my name a link.
    If it's a non-officer, and I'm an admin, link to the person edit page
    If it's a non-officer, and I'm a staff member, don't make it a link
    Context should be the request context as populated by OfficerDetailView()
    """
    if other_person.pk == context.get('object').pk:
        template = Template("<span class='associate-self'>{{ person.name }}</span>")
        return template.render(context)
    elif other_person.is_law_enforcement is False and context.get('is_admin'):
        template = Template(f"<a href='{ other_person.get_edit_url }'>{ other_person.name }</a>")
        return template.render(context)
    elif other_person.is_law_enforcement is False and context.get('is_admin') is False:
        template = Template(f"{other_person.name}")
        return template.render(context)
    else:
        template = Template(f"<a href='{ other_person.get_profile_url }' class='associate-link'>{ other_person.name }</a>")
        return template.render(context)


@register.filter
def format_identifiers(identifiers: list) -> str:
    """Returns a concatenated string of the identifier values from a list of identifier objects
    """
    if identifiers:
        identifiers_values = []
        for identifier in identifiers:
            identifiers_values.append(identifier.identifier)
        return f"({', '.join(identifiers_values)})"
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

@register.filter
def table_cell(input_value):
    if input_value:
        return input_value
    else:
        return mark_safe("<span class='empty-table-field'>&mdash;</span>")

@register.filter
def table_cell_currency(input_value):
    if input_value:
        return f"${input_value}"
    else:
        return mark_safe("<span class='empty-table-field'>&mdash;</span>")
