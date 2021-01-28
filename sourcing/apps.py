from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class SourcingAppConfig(AppConfig):
    """ Configuration settings for sourcing app.

    """
    name = 'sourcing'
    verbose_name = _('Sourcing data')
