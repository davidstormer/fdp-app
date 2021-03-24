from django import template
from inheritable.models import AbstractConfiguration


register = template.Library()


@register.simple_tag
def num_of_secs_between_data_wizard_import_status_checks():
    """ Retrieves the number of seconds to wait between each asynchronous GET request that is used to check on the
    status of importing records with the Django Data Wizard package.

    Will be used to set the data-wq-interval attribute value in the progress element.

    See: https://github.com/wq/django-data-wizard/tree/main/packages/progress

    :return: Number of seconds to wait between each asynchronous request.
    """
    return AbstractConfiguration.num_of_secs_between_data_wizard_import_status_checks()
