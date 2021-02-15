"""fdp URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.views.defaults import page_not_found
from two_factor.urls import urlpatterns as two_factor__urls
from two_factor.views import BackupTokensView, ProfileView, QRGeneratorView, SetupCompleteView, SetupView
from two_factor.admin import AdminSiteOTPRequired
from fdpuser.views import FdpPasswordResetView, FdpLoginView
from inheritable.models import AbstractConfiguration


# Django Two-Factor Authentication
# Enforce OTP for admin page access
# See: https://django-two-factor-auth.readthedocs.io/en/stable/implementing.html
# See: https://docs.djangoproject.com/en/2.0/ref/contrib/admin/#hooking-adminsite-instances-into-your-urlconf
admin.site.__class__ = AdminSiteOTPRequired


# If the configuration supports Azure Active Directory, then use the extended login view for the 2FA process
# to allow users to skip the password authentication step if they have already authenticated via Azure AD
two_factor_base_route = ''
if AbstractConfiguration.can_do_azure_active_directory():
    # Copied from Django Two-Factor Authentication package /two-factor/urls.py version 1.13
    # See: https://github.com/Bouke/django-two-factor-auth/
    two_factor_core_paths = [
        path('account/login/', FdpLoginView.as_view(), name='login',),
        path('account/two_factor/setup/', SetupView.as_view(), name='setup',),
        path('account/two_factor/qrcode/', QRGeneratorView.as_view(), name='qr',),
        path('account/two_factor/setup/complete/', SetupCompleteView.as_view(), name='setup_complete',),
        path('account/two_factor/backup/tokens/', BackupTokensView.as_view(), name='backup_tokens',),
        # Removed view to register a backup phone:  account/two_factor/backup/phone/register/
        # Removed view to unregister a backup phone: 'account/two_factor/backup/phone/unregister/<int:pk>/
    ]
    two_factor_profile_paths = [
        path('account/two_factor/', ProfileView.as_view(), name='profile',),
        # Removed view to disable 2FA: account/two_factor/disable/
    ]
    two_factor_urls_list = [
        path(two_factor_base_route, include((two_factor_core_paths + two_factor_profile_paths, 'two_factor'))),
    ]
else:
    two_factor_urls_list = [
        # The following URL is disabled, so that a user cannot disable their 2FA once it is enabled
        path('{b}account/two_factor/disable/'.format(b=two_factor_base_route), page_not_found,
             {'exception': Exception('This page is disabled')}),
        # URLs for Django Two-Factor Authentication package
        # see: https://github.com/Bouke/django-two-factor-auth
        path(two_factor_base_route, include(two_factor__urls)),
    ]


urlpatterns = [
    # The following URL is disabled, so that a user cannot change their password without verifying their email
    path('admin/password_change/', page_not_found, {'exception': Exception('This page is disabled')}),
    path('admin/', admin.site.urls),
] + two_factor_urls_list + (
    # only include URLs for social_django package is external authentication through Azure Active Directory is supported
    [] if not AbstractConfiguration.can_do_azure_active_directory() else [
        # URLs for authenticating via Microsoft Azure Active Directory
        path('social/', include('social_django.urls', namespace='social')),
    ]
) + [
    # URL for logging out
    path('account/logout/', view=auth_views.LogoutView.as_view(), name='logout'),
] + (
    # only include URLs for password reset if the configuration supports it
    [] if not AbstractConfiguration.can_do_password_reset() else [
        # URLs for resetting passwords through a tokenized link
        path('password/reset/', FdpPasswordResetView.as_view(), name='password_reset'),
    ]
) + [
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
    # Django Data Wizard: https://github.com/wq/django-data-wizard
    path('datawizard/', include('data_wizard.urls')),
]
