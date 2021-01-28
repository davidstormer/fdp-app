from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class FdpUserAppConfig(AppConfig):
    """ Configuration settings for FDP user app.

    """
    name = 'fdpuser'
    verbose_name = _('Authentication')
