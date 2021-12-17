from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class FdpUserAppConfig(AppConfig):
    """ Configuration settings for FDP user app.

    """
    name = 'fdpuser'
    verbose_name = _('Authentication')

    def ready(self):
        """ Patches Django's Admin site to require 2FA through the Django Two-Factor Authentication package, and also
        optionally integrates the federated login page.

        Based on the two_factor.apps.TwoFactorConfig.ready(...) method.

        :return: Nothing.
        """
        if getattr(settings, 'TWO_FACTOR_PATCH_ADMIN', True):
            from .admin import patch_fdp_admin
            patch_fdp_admin()
