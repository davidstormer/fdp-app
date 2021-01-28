from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class SupportingAppConfig(AppConfig):
    """ Configuration settings for supporting app.

    """
    name = 'supporting'
    verbose_name = _('Supporting data')
