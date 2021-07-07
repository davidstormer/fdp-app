from django.urls import path
from inheritable.models import AbstractUrlValidator, AbstractConfiguration
from . import views


app_name = 'fdpuser'


urlpatterns = [
    path(AbstractUrlValidator.FDP_USER_SETTINGS_URL, views.SettingsTemplateView.as_view(), name='settings'),
] + (
    # only include URLs for password change if the configuration supports it
    [] if not AbstractConfiguration.can_do_password_reset() else [
        path(
            AbstractUrlValidator.FDP_USER_CONF_PWD_CHNG_URL,
            views.ConfirmPasswordChangeTemplateView.as_view(),
            name='confirm_password_change'
        ),
    ]
) + [
    path(AbstractUrlValidator.FDP_USER_CONF_2FA_RESET_URL, views.ConfirmTwoFactorResetTemplateView.as_view(),
         name='confirm_2fa_reset'),
    path(AbstractUrlValidator.FDP_USER_CHNG_PWD_URL, views.ResetPasswordRedirectView.as_view(),
         name='change_password'),
    path(AbstractUrlValidator.FDP_USER_RESET_2FA_URL, views.ResetTwoFactorRedirectView.as_view(),
         name='reset_2fa'),
    path(AbstractUrlValidator.ASYNC_RENEW_SESSION_URL,
         views.AsyncRenewSessionView.as_view(), name='async_renew_session'),
]
