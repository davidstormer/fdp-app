from django.test import Client, override_settings
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.contrib import admin
from fdpuser.admin import FdpAdminSiteOTPRequired
from fdpuser.models import FdpUser
from fdpuser.views import FdpLoginView
from inheritable.models import AbstractConfiguration
from inheritable.tests import azure_test_settings_required
from fdp.urlconf.constants import CONST_LOGIN_URL_NAME
from fdpuser.tests.common import FdpUserCommonTestCase

import logging
logger = logging.getLogger(__name__)


class FdpUserAzureTestCase(FdpUserCommonTestCase):

    @azure_test_settings_required
    @override_settings(
        ROOT_URLCONF='fdp.urlconf.test.federated_login_azure_urls',
        FEDERATED_LOGIN_OPTIONS=[{'label': '...', 'url_pattern_name': 'two_factor:login', 'url_pattern_args': []}]
    )
    def test_federated_login_for_azure(self):
        """ Test federated login is integrated during Azure settings, including:
            (a) Federated login page appears first for all permutations of user roles when user is not authenticated;
            and
            (b) Federated login page does not appear for all permutations of user roles when user is authenticated.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for federated login for Azure settings'))
        self.exercise_federated_login_for_all()
        logger.debug(_('\nSuccessfully finished test for federated login for Azure settings\n\n'))

    @azure_test_settings_required
    def test_azure_configuration(self):
        """ Test login view, 2FA, URL patterns and file serving for a configuration that is intended for a
        Microsoft Azure environment.

        User authentication occurs through BOTH the Django backend and Azure Active Directory.

        Files are served through the Azure mechanism only.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for login view, 2FA, URL patterns and '
                       'file serving for Microsoft Azure configuration'))
        # test is only relevant for Microsoft Azure configuration
        self.assertFalse(AbstractConfiguration.is_using_local_configuration())
        self.assertTrue(AbstractConfiguration.is_using_azure_configuration())
        self.assertTrue(AbstractConfiguration.can_do_azure_active_directory())
        self.assertFalse(AbstractConfiguration.use_only_azure_active_directory())
        logger.debug(
            'Checking that view for login is from custom extension of Django Two-Factor Authentication package')
        c = Client(**self._local_client_kwargs)
        # redirect to login expected
        response = self._do_get(
            c=c,
            url='/',
            expected_status_code=302,
            login_startswith=reverse('two_factor:{n}'.format(n=CONST_LOGIN_URL_NAME))
        )
        # follow redirect
        response = self._do_get(c=response.client, url=response.url, expected_status_code=200, login_startswith=None)
        # assert that the default 2FA Login view is used to receive username and password
        self._assert_class_based_view(response=response, expected_view=FdpLoginView)
        logger.debug('Checking that 2FA is encountered after Django authentication with username and password')
        host_admin = self._create_fdp_user(email_counter=FdpUser.objects.all().count() + 1, **self._host_admin_dict)
        # user is authenticable by Django backend
        self.assertFalse(FdpUser.is_user_azure_authenticated(user=host_admin))
        user_kwargs = {'username': host_admin.email, 'password': self._password, 'login_status_code': 200}
        self._create_2fa_record(user=host_admin)
        response = self._do_django_username_password_authentication(c=response.client, **user_kwargs)
        self.assertEqual(response.status_code, 200)
        # default 2FA Login view is expected for OTP step
        self._assert_2fa_step_in_login_view(response=response, expected_view=FdpLoginView)
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
        response = self._do_django_username_password_authentication(c=response.client, **user_kwargs)
        # default 2FA Login view is expected for username/password step
        self._assert_username_and_password_step_in_login_view(response=response, expected_view=FdpLoginView)
        logger.debug('Checking that 2FA is enforced for the Admin site')
        self.assertEqual(admin.site.__class__, FdpAdminSiteOTPRequired)
        logger.debug('Checking that Azure users skip 2FA step')
        self.check_azure_user_skips_2fa(has_django_auth_backend=True)
        logger.debug(_('\nSuccessfully finished test for '
                       'login view, 2FA, URL patterns and file serving for Microsoft Azure configuration\n\n'))
