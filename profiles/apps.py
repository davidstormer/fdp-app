from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class ProfilesAppConfig(AppConfig):
    """ Configuration settings for profiles app.

    """
    name = 'profiles'
    verbose_name = _('Profile Log')
    verbose_name_plural = _('Profile Logs')
