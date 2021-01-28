from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class CoreAppConfig(AppConfig):
    """ Configuration settings for core app.

    """
    name = 'core'
    verbose_name = _('Core data')
