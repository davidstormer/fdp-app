from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, re_path, include
from django.conf import settings
from django.views.defaults import page_not_found
from fdpuser.admin import FdpAdminSiteOTPRequired
from fdpuser.views import FdpPasswordResetView, DownloadEulaFileView, FederatedLoginTemplateView
from inheritable.models import AbstractUrlValidator, AbstractConfiguration


# Django Two-Factor Authentication
# Enforce OTP for admin page access
# See: https://django-two-factor-auth.readthedocs.io/en/stable/implementing.html
# See: https://docs.djangoproject.com/en/2.0/ref/contrib/admin/#hooking-adminsite-instances-into-your-urlconf
# Also, optionally integrates the federated login page if supported by the current configuration.
admin.site.__class__ = FdpAdminSiteOTPRequired


#: URL patterns for Admin site.
admin_urlpatterns = [
    # The following URL is disabled, so that a user cannot change their password without verifying their email
    path('admin/password_change/', page_not_found, {'exception': Exception('This page is disabled')}),
    path('admin/', admin.site.urls),
]


#: URL patterns for log out view.
logout_urlpatterns = [
    # URL for logging out
    path('account/logout/', view=auth_views.LogoutView.as_view(), name='logout'),
]


#: URL patterns for the majority of the system, including the Django apps.
rest_urlpatterns = [
    path('password/reset/sent/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('password/reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    # Disabled for Django Two-Factor Authentication
    # path('admin/', include('django.contrib.auth.urls')),
    path('cspreports/', include('cspreports.urls')),
    path('fdp/user/', include('fdpuser.urls', namespace='fdpuser')),
    path('', include('bulk.urls', namespace='bulk')),
    path('', include('changing.urls', namespace='changing')),
    path('', include('profiles.urls', namespace='profiles')),
    path('', include('core.urls', namespace='core')),
    path('', include('sourcing.urls', namespace='sourcing')),
    path('', include('wholesale.urls', namespace='wholesale')),
    # Django Data Wizard: https://github.com/wq/django-data-wizard
    path('datawizard/', include('data_wizard.urls')),
]
#: Only include the EULA download link if the configuration supports it.
if AbstractConfiguration.eula_splash_enabled():
    # EULA download URL pattern included here instead of through fdp.urls so that it is outside of base path for app.
    rest_urlpatterns += [
        re_path(
            r'{b}{s}(?P<path>.*)'.format(
                b=settings.FDP_MEDIA_URL[1:] if settings.FDP_MEDIA_URL.startswith('/') else settings.FDP_MEDIA_URL,
                s=AbstractUrlValidator.EULA_BASE_URL
            ),
            view=DownloadEulaFileView.as_view(),
            name='download_eula_file'
        ),
    ]


#: URL patterns for when password resets are not supported.
cannot_do_password_reset_urlpatterns = []


#: URL patterns for when password resets are supported.
can_do_password_reset_urlpatterns = [
    # URLs for resetting passwords through a tokenized link
    path('password/reset/', FdpPasswordResetView.as_view(), name='password_reset'),
]


#: Only include the federated login link if the configuration supports it.
if AbstractConfiguration.can_do_federated_login():
    rest_urlpatterns += [
        path(
            AbstractUrlValidator.FDP_USER_FEDERATED_LOGIN_URL,
            FederatedLoginTemplateView.as_view(),
            name='federated_login'
        )
    ]
