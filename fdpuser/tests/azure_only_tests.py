from django.test import Client, override_settings
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.contrib import admin
from django.views.generic.base import RedirectView
from fdpuser.admin import FdpAdminSiteOTPRequired
from fdpuser.models import FdpUser
from inheritable.models import AbstractConfiguration
from inheritable.tests import azure_only_test_settings_required
from fdp.urlconf.constants import CONST_TWO_FACTOR_PROFILE_URL_NAME, CONST_LOGIN_URL_NAME
from fdpuser.tests.common import FdpUserCommonTestCase

import logging
logger = logging.getLogger(__name__)


class FdpUserAzureOnlyTestCase(FdpUserCommonTestCase):
    @azure_only_test_settings_required
    @override_settings(
        ROOT_URLCONF='fdp.urlconf.test.federated_login_azure_urls',
        FEDERATED_LOGIN_OPTIONS=[{'label': '...', 'url_pattern_name': 'two_factor:login', 'url_pattern_args': []}]
    )
    def test_federated_login_for_azure_only(self):
        """ Test federated login is integrated during Azure-only settings, including:
            (a) Federated login page appears first for all permutations of user roles when user is not authenticated;
            and
            (b) Federated login page does not appear for all permutations of user roles when user is authenticated.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for federated login for Azure-only settings'))
        self.exercise_federated_login_for_all()
        logger.debug(_('\nSuccessfully finished test for federated login for Azure-only settings\n\n'))

    @azure_only_test_settings_required
    def test_azure_only_configuration(self):
        """ Test login view, 2FA, URL patterns and file serving for a configuration that is intended for a
        Microsoft Azure environment.

        User authentication occurs through ONLY Azure Active Directory.

        Files are served through the Azure mechanism only.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for login view, 2FA, URL patterns and '
                       'file serving for "only" Microsoft Azure configuration'))
        # test is only relevant for "only" Microsoft Azure configuration
        self.assertFalse(AbstractConfiguration.is_using_local_configuration())
        self.assertTrue(AbstractConfiguration.is_using_azure_configuration())
        self.assertTrue(AbstractConfiguration.can_do_azure_active_directory())
        self.assertTrue(AbstractConfiguration.use_only_azure_active_directory())
        logger.debug('Checking that view for login redirects to social auth with Azure Active Directory provider')
        c = Client(**self._local_client_kwargs)
        # redirect to login expected, which is itself a redirect view
        response = self._do_get(
            c=c,
            url='/',
            expected_status_code=302,
            login_startswith=reverse('two_factor:{n}'.format(n=CONST_LOGIN_URL_NAME))
        )
        # redirect to social auth login expected
        response = self._do_get(
            c=response.client,
            url=response.url,
            expected_status_code=302,
            login_startswith=reverse('social:begin', args=[AbstractConfiguration.azure_active_directory_provider])
        )
        self._assert_class_based_view(response=response, expected_view=RedirectView)
        logger.debug('Checking that non-Azure users cannot log in')
        host_admin = self._create_fdp_user(email_counter=FdpUser.objects.all().count() + 1, **self._host_admin_dict)
        self.assertFalse(FdpUser.is_user_azure_authenticated(user=host_admin))
        self._create_2fa_record(user=host_admin)
        response = self.verify_user_cannot_log_in(c=response.client, user=host_admin)
        logger.debug('Checking that social-auth login is defined')
        self.assertIsNotNone(reverse('social:begin', args=[AbstractConfiguration.azure_active_directory_provider]))
        for static_file_type in self.get_static_file_types(callable_name='serve_azure_storage_static_file'):
            logger.debug('Checking that {t} files are served '
                         'using serve_azure_storage_static_file(...) method'.format(t=static_file_type['type']))
            self.check_callable_serving_static(
                user=host_admin,
                path_kwargs=static_file_type['path_kwargs'],
                view_name=static_file_type['view_name'],
                expected_callable=static_file_type['expected_callable'],
                view_class=static_file_type['view_class']
            )
        logger.debug('Checking that users with only_external_auth=True cannot log in with username and password')
        host_admin.only_external_auth = True
        host_admin.save()
        response = self.verify_user_cannot_log_in(c=response.client, user=host_admin)
        logger.debug('Checking that Django Two-Factor Authentication profile is not defined')
        self._do_get(
            c=response.client,
            url=reverse('two_factor:{p}'.format(p=CONST_TWO_FACTOR_PROFILE_URL_NAME)),
            expected_status_code=404,
            login_startswith=None
        )
        logger.debug('Checking that 2FA is enforced for the Admin site')
        self.assertEqual(admin.site.__class__, FdpAdminSiteOTPRequired)
        logger.debug('Checking that Azure users skip 2FA step')
        self.check_azure_user_skips_2fa(has_django_auth_backend=False)
        logger.debug(_('\nSuccessfully finished test for '
                       'login view, 2FA, URL patterns and file serving for "only" Microsoft Azure configuration\n\n'))
