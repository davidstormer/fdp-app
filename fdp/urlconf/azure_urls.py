from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from two_factor.views import BackupTokensView, ProfileView, QRGeneratorView, SetupCompleteView, SetupView
from fdpuser.views import FdpLoginView
from fdp.configuration.abstract.constants import CONST_AZURE_AD_PROVIDER
from .constants import CONST_TWO_FACTOR_BASE_ROUTE, CONST_LOGIN_URL_PATH, CONST_LOGIN_URL_NAME, \
    CONST_TWO_FACTOR_PROFILE_URL_NAME, CONST_TWO_FACTOR_PROFILE_URL_PATH


#: Import URL patterns that are shared by all configurations.
from .base_urls import *


# Configuration supports only Azure Active Directory as a user authentication backend, so disable 2FA profile view
# and redirect login automatically to Azure
if AbstractConfiguration.use_only_azure_active_directory():
    two_factor_core_paths = [
        path(
            CONST_LOGIN_URL_PATH,
            RedirectView.as_view(url=reverse_lazy('social:begin', args=[CONST_AZURE_AD_PROVIDER])),
            name=CONST_LOGIN_URL_NAME
        ),
    ]
    two_factor_profile_paths = [
        path(CONST_TWO_FACTOR_PROFILE_URL_PATH, page_not_found, name=CONST_TWO_FACTOR_PROFILE_URL_NAME,
             kwargs={'exception': Exception('This page is disabled')}),
    ]
# Configuration supports both Azure Active Directory and Django as user authentication backends
else:
    # Copied from Django Two-Factor Authentication package /two-factor/urls.py version 1.13
    # See: https://github.com/Bouke/django-two-factor-auth/
    two_factor_core_paths = [
        path(CONST_LOGIN_URL_PATH, FdpLoginView.as_view(), name=CONST_LOGIN_URL_NAME,),
        path('account/two_factor/setup/', SetupView.as_view(), name='setup',),
        path('account/two_factor/qrcode/', QRGeneratorView.as_view(), name='qr',),
        path('account/two_factor/setup/complete/', SetupCompleteView.as_view(), name='setup_complete',),
        path('account/two_factor/backup/tokens/', BackupTokensView.as_view(), name='backup_tokens',),
        # Removed view to register a backup phone:  account/two_factor/backup/phone/register/
        # Removed view to unregister a backup phone: 'account/two_factor/backup/phone/unregister/<int:pk>/
    ]
    two_factor_profile_paths = [
        path(CONST_TWO_FACTOR_PROFILE_URL_PATH, ProfileView.as_view(), name=CONST_TWO_FACTOR_PROFILE_URL_NAME),
        # Removed view to disable 2FA: account/two_factor/disable/
    ]
# compile authentication and 2FA related URLs
two_factor_urlpatterns = [
    path(CONST_TWO_FACTOR_BASE_ROUTE, include((two_factor_core_paths + two_factor_profile_paths, 'two_factor'))),
]


urlpatterns = admin_urlpatterns + two_factor_urlpatterns + (
    # only include URLs for social_django package is external authentication through Azure Active Directory is supported
    [] if not AbstractConfiguration.can_do_azure_active_directory() else [
        # URLs for authenticating via Microsoft Azure Active Directory
        path('social/', include('social_django.urls', namespace='social')),
    ]
) + logout_urlpatterns + (
    cannot_do_password_reset_urlpatterns if not AbstractConfiguration.can_do_password_reset()
    else can_do_password_reset_urlpatterns
) + rest_urlpatterns
