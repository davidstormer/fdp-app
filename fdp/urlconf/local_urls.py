from two_factor.urls import urlpatterns as two_factor__urls
from inheritable.models import AbstractConfiguration
from .constants import CONST_TWO_FACTOR_BASE_ROUTE


#: Import URL patterns that are shared by all configurations.
from .base_urls import *


urlpatterns = admin_urlpatterns + [
    # The following URL is disabled, so that a user cannot disable their 2FA once it is enabled
    path('{b}account/two_factor/disable/'.format(b=CONST_TWO_FACTOR_BASE_ROUTE), page_not_found,
         {'exception': Exception('This page is disabled')}),
    # URLs for Django Two-Factor Authentication package
    # see: https://github.com/Bouke/django-two-factor-auth
    path(CONST_TWO_FACTOR_BASE_ROUTE, include(two_factor__urls)),
] + logout_urlpatterns + (
    cannot_do_password_reset_urlpatterns if not AbstractConfiguration.can_do_password_reset()
    else can_do_password_reset_urlpatterns
) + rest_urlpatterns
