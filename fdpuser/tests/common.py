from django.test import Client, RequestFactory
from django.utils.timezone import now
from django.urls import reverse, NoReverseMatch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.apps import apps
from fdpuser.models import FdpUser, PasswordReset
from fdpuser.forms import FdpUserChangeForm
from bulk.views import DownloadImportFileView
from inheritable.models import AbstractConfiguration
from inheritable.tests import AbstractTestCase
from sourcing.models import Attachment, Content, ContentPerson
from sourcing.views import DownloadAttachmentView
from core.models import Person
from core.views import DownloadPersonPhotoView
from fdp.configuration.abstract.constants import CONST_AZURE_AUTH_APP
from fdp.urlconf.constants import CONST_LOGIN_URL_NAME
from unittest.mock import patch as mock_patch
from os import environ
import logging

logger = logging.getLogger(__name__)


class FdpUserCommonTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test access to views:
            (a) For all user types

    (2) Test throttling for password resets and password changes
            (a) For all user types

    (3) Test Guest Admin accessing all permutations of user roles

    (4) Test Guest Admin create new user (check that organizations match)

    (5) Test Admin permission escalation

    (6) Test Guest Admin access to host-only views

    (7) Test login view, 2FA, URL patterns and file serving for local development configuration

    (8) Test login view, 2FA, URL patterns and file serving for Microsoft Azure configuration

    (9) Test login view, 2FA, URL patterns and file serving for Microsoft Azure configuration with only AAD
    authentication

    (10) Test enforcement of EULA requirement, including:
            (a) EULA is not required when EULAs are disabled;
            (b) EULA agreement is first required before accessing profiles and changing index pages; and
            (c) EULA agreement is only required once when accessing profiles and changing index pages.

    (11) Test federated login is integrated during local settings, including:
            (a) Federated login page appears first for all permutations of user roles when user is not authenticated;
            and
            (b) Federated login page does not appear for all permutations of user roles when user is authenticated.

    (12) Test federated login is integrated during Azure settings, including:
            (a) Federated login page appears first for all permutations of user roles when user is not authenticated;
            and
            (b) Federated login page does not appear for all permutations of user roles when user is authenticated.

    (13) Test federated login is integrated during Azure-only settings, including:
            (a) Federated login page appears first for all permutations of user roles when user is not authenticated;
            and
            (b) Federated login page does not appear for all permutations of user roles when user is authenticated.

    """
    def setUp(self):
        """ Configure RECPATCHA to be in test mode.

        :return: Nothing.
        """
        # skip setup and tests unless configuration is compatible
        super().setUp()
        # used to test password resets
        environ[self._recaptcha] = 'True'
        # create a bulk import file
        self._add_fdp_import_file()
        # create a person photo
        self._add_person_photo()
        # create an attachment
        self._add_attachment()

    def tearDown(self):
        """ Configure RECAPTCHA to no longer be in test mode.
        """
        environ[self._recaptcha] = 'False'

    #: Suffix for user email for user without organization.
    without_org_suffix = '_without_org'

    #: Suffix for user email for user with correct organization.
    with_org_suffix = '_with_org'

    #: Suffix for user email for user with incorrect organization.
    wrong_org_suffix = '_wrong_org'

    def verify_user_cannot_log_in(self, c, user):
        """ Verifies that user cannot log in through Django authentication.

        :param c: Instantiated testing client for Django.
        :param user: User to verify.
        :return: Http response that is returned by GET request to access homepage.
        """
        # except 400 Bad Request, because view is not configured to handle POST request for login
        response = self._do_django_username_password_authentication(
            c=c,
            username=user.email,
            password=self._password,
            login_status_code=400,
            # if not specified, reverse will attempt to convert '/social/login/azu...'
            override_login_url=reverse('two_factor:{n}'.format(n=CONST_LOGIN_URL_NAME))
        )
        # override and try anyway to force a login
        response.client.force_login(user=user, backend=None)
        # verify redirect to login screen
        response = self._do_get(
            c=response.client,
            url='/',
            expected_status_code=302 if not user.only_external_auth else 400,
            login_startswith=reverse('two_factor:{n}'.format(n=CONST_LOGIN_URL_NAME))
        )
        return response

    def get_static_file_types(self, callable_name):
        """ Retrieves a list of dictionaries representing types of static files that can be served by views for download
        by the user.

        :param callable_name: Name of method is called to serve static files.

        :return: List of dictionaries.
        """
        return [
            {
                'type': 'bulk import',
                'path_kwargs': {'path': self._get_fdp_import_file_file_path_for_view()},
                'view_name': 'bulk:download_import_file',
                'expected_callable': f'bulk.views.DownloadImportFileView.{callable_name}',
                'view_class': DownloadImportFileView
            },
            {
                'type': 'person photo',
                'path_kwargs': {'path': self._get_person_photo_file_path_for_view()},
                'view_name': 'core:download_person_photo',
                'expected_callable': f'core.views.DownloadPersonPhotoView.{callable_name}',
                'view_class': DownloadPersonPhotoView
            },
            {
                'type': 'attachment',
                'path_kwargs': {'path': self._get_attachment_file_path_for_view()},
                'view_name': 'sourcing:download_attachment',
                'expected_callable': f'sourcing.views.DownloadAttachmentView.{callable_name}',
                'view_class': DownloadAttachmentView
            }
        ]

    def check_emails_not_in_response(self, email, response_content):
        """ Checks that email addresses with all three suffixes are not appearing in the string representation of the
        HTTP response that was returned through a view.

        :param email: Base email to check for.
        :param response_content: String representation of the HTTP response that was returned.
        :return: Nothing.
        """
        self.assertNotIn('{email}{suffix}'.format(email=email, suffix=self.without_org_suffix), response_content)
        self.assertNotIn('{email}{suffix}'.format(email=email, suffix=self.with_org_suffix), response_content)
        self.assertNotIn('{email}{suffix}'.format(email=email, suffix=self.wrong_org_suffix), response_content)

    def add_fdp_users(self, fdp_org, other_fdp_org):
        """ Adds the FDP users that will be tested.

        :param fdp_org: FDP organization to which a FDP user can be linked.
        :param other_fdp_org: Another FDP organization to which a FDP user can be linked.
        :return: A tuple:
                    List of IDs of users without FDP organization,
                    list of IDs of users with FDP organization,
                    list of IDs of users with another FDP organization.
        """
        without_org_ids = {}
        with_org_ids = {}
        wrong_org_ids = {}
        # for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # email address will contain uniquely identifiable string
            email = (user_role[self._label]).replace(' ', '').lower()
            # create the FDP user in the test database
            without_org_fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email='{email}{withoutorg}@google.com'.format(email=email, i=i, withoutorg=self.without_org_suffix)
            )
            without_org_ids[email] = without_org_fdp_user.pk
            # create the FDP user in the test database
            with_org_fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email='{email}{withorg}@google.com'.format(email=email, i=i, withorg=self.with_org_suffix)
            )
            with_org_fdp_user.fdp_organization = fdp_org
            with_org_fdp_user.full_clean()
            with_org_fdp_user.save()
            with_org_ids[email] = with_org_fdp_user.pk
            # create the FDP user in the test database
            other_org_fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email='{email}{wrongorg}@freedobject.com'.format(email=email, i=i, wrongorg=self.wrong_org_suffix)
            )
            other_org_fdp_user.fdp_organization = other_fdp_org
            other_org_fdp_user.full_clean()
            other_org_fdp_user.save()
            wrong_org_ids[email] = other_org_fdp_user.pk
        return without_org_ids, with_org_ids, wrong_org_ids

    def get_changelist_response(self, fdp_user):
        """ Retrieves a response after sending a request to the admin changelist view for FDP User.

        :param fdp_user: FDP user sending request.
        :return: String representation of the response.
        """
        return self._get_response_from_get_request(
            fdp_user=fdp_user,
            url=reverse('admin:fdpuser_fdpuser_changelist'),
            expected_status_code=200,
            login_startswith=None
        )

    def get_change_response(self, fdp_user, expected_status_code, login_startswith, pk):
        """ Retrieves a response when sending a request to the admin change instance view for FDP.

        :param fdp_user: FDP user sending request.
        :param expected_status_code: Expected HTTP status code that is returned in the response.
        :param login_startswith: Url to which response may be redirected. Only used when HTTP status code is 302.
        :param pk: Primary key for model instance to change.
        :return: String representation of the response.
        """
        return self._get_response_from_get_request(
            fdp_user=fdp_user,
            url=reverse('admin:fdpuser_fdpuser_change', args=(pk,)),
            expected_status_code=expected_status_code,
            login_startswith=login_startswith
        )

    def get_history_response(self, fdp_user, expected_status_code, login_startswith, pk):
        """ Retrieves a response when sending a request to the admin history view for FDP.

        :param fdp_user: FDP user sending request.
        :param expected_status_code: Expected HTTP status code that is returned in the response.
        :param login_startswith: Url to which response may be redirected. Only used when HTTP status code is 302.
        :param pk: Primary key for model instance for which to retrieve history.
        :return: String representation of the response.
        """
        return self._get_response_from_get_request(
            fdp_user=fdp_user,
            url=reverse('admin:fdpuser_fdpuser_history', args=(pk,)),
            expected_status_code=expected_status_code,
            login_startswith=login_startswith
        )

    def get_delete_response(self, fdp_user, expected_status_code, login_startswith, pk):
        """ Retrieves a response when sending a request to the admin delete instance view for FDP.

        :param fdp_user: FDP user sending request.
        :param expected_status_code: Expected HTTP status code that is returned in the response.
        :param login_startswith: Url to which response may be redirected. Only used when HTTP status code is 302.
        :param pk: Primary key for model instance to delete.
        :return: String representation of the response.
        """
        return self._get_response_from_get_request(
            fdp_user=fdp_user,
            url=reverse('admin:fdpuser_fdpuser_delete', args=(pk,)),
            expected_status_code=expected_status_code,
            login_startswith=login_startswith
        )

    def delete_password_resets(self):
        """ Removes all password reset records from the test database.

        :return: Nothing.
        """
        PasswordReset.objects.all().delete()
        self.assertEqual(PasswordReset.objects.all().count(), 0)

    def add_data_for_officer_profile(self):
        """ Add data to create a basic version of the officer profile, including the enabling functionality to download
        all attachments for the profile.

        :return: Nothing.
        """
        # officer (whose profile will be accessed below)
        officer = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        # connection between attachment and officer
        content = Content.objects.create(name='Content1', **self._not_confidential_dict)
        # Use SimpleUploadedFile to populate dummy file for testing download functionality in officer profile
        dummy_file = SimpleUploadedFile("dummy_file.txt", b"This is a test file")
        attachment = Attachment.objects.create(name='dummy', file=dummy_file)
        content.attachments.add(attachment)
        ContentPerson.objects.create(person=officer, content=content)
        # This primary key will be used in tests when referencing self._views
        self.assertNotEqual(self._default_pk, officer.pk)
        self._default_pk = officer.pk

    def check_perm_escalate(self, user_to_change, user_changing, perm_escalation_dict):
        """ Check the permission escalation for a particular user by a particular user.

        :param user_to_change: User that is being changed during the permission escalation attempt.
        :param user_changing: User that is doing the changing during the permission escalation attempt.
        :param perm_escalation_dict: The dictionary of keyword arguments that will be expanded to define the permission
        escalation in the cleaned data portion of the FdpUserChangeForm.
        :return: Nothing.
        """
        # values for user before permission escalation is attempted
        prev_fdp_organization = user_to_change.fdp_organization
        prev_is_host = user_to_change.is_host
        prev_is_superuser = user_to_change.is_superuser
        # simulate change form
        change_form = FdpUserChangeForm(instance=user_to_change)
        request = self.UserRequest()
        request.user = user_changing
        change_form.request = request
        change_form.cleaned_data = {'email': user_to_change.email, **perm_escalation_dict}
        changed_user = change_form.save(commit=True)
        database_user = FdpUser.objects.get(pk=changed_user.pk)
        # compare values before and after permission escalation attempt
        if prev_fdp_organization is None:
            self.assertTrue(changed_user.fdp_organization is None)
            self.assertTrue(database_user.fdp_organization is None)
        else:
            self.assertEqual(prev_fdp_organization, changed_user.fdp_organization)
            self.assertEqual(prev_fdp_organization, database_user.fdp_organization)
        self.assertEqual(prev_is_host, changed_user.is_host)
        self.assertEqual(prev_is_host, database_user.is_host)
        self.assertEqual(prev_is_superuser, changed_user.is_superuser)
        self.assertEqual(prev_is_superuser, database_user.is_superuser)

    @staticmethod
    def delete_data_for_officer_profile():
        """ Deletes data that may have been created for the officer profile.

        :return: Nothing.
        """
        ContentPerson.objects.all().delete()
        Content.objects.all().delete()
        Attachment.objects.all().delete()
        Person.objects.all().delete()

    @staticmethod
    def tautology():
        """ Always returns True.

        Used to dynamically add a callable to the user instance, so that when is_verified() is called by the 2FA
        middleware, the user is verified.

        :return: Always true.
        """
        return True

    @staticmethod
    def add_user_social_auth(azure_user):
        """ Creates a user social auth record for a user authenticated through the Azure Active Directory backend.

        :param azure_user: User authenticated through the Azure Active Directory backend.
        :return: Nothing.
        """
        user_social_auth_model = apps.get_model(CONST_AZURE_AUTH_APP, 'UserSocialAuth')
        user_social_auth_model.objects.create(
            user=azure_user,
            uid=str(user_social_auth_model.objects.all().count()),
            provider=AbstractConfiguration.azure_active_directory_provider
        )

    def check_azure_user_skips_2fa(self, has_django_auth_backend):
        """ Checks authentication steps for a user who is expected to be authenticated through Azure Active Directory.

        :param has_django_auth_backend: True if Django authentication backend is enabled, false if it is disabled.
        :return: Nothing.
        """
        enable_2fa_txt = 'Enable 2FA'
        azure_user = self._create_fdp_user(email_counter=FdpUser.objects.all().count() + 1, **self._host_admin_dict)
        c = Client(**self._local_client_kwargs)
        # force username/password authentication for newly added user, but 2FA is not yet validated
        c.force_login(user=azure_user, backend=None)
        # confirm user requires 2FA
        try:
            response = self._do_get(c=c, url='/', expected_status_code=403, login_startswith=None)
            self.assertIn(enable_2fa_txt, str(response.content))
        # if Django authentication backend is disabled, then NoReverseMatch is expected for the 'setup' pattern name
        # (since 2FA is not fully configured)
        except NoReverseMatch as err:
            self.assertIn('setup', str(err))
            # exception should only be raised if Django authentication backend is disabled
            self.assertFalse(has_django_auth_backend)
        # change user so that they are externally authenticable, and have a social auth link
        azure_user.only_external_auth = True
        azure_user.save()
        self.add_user_social_auth(azure_user=azure_user)
        # confirm user does not require 2FA
        response = self._do_get(c=c, url='/', expected_status_code=200, login_startswith=None)
        self.assertNotIn(enable_2fa_txt, str(response.content))
        # change user so that they are a superuser
        azure_user.is_superuser = True
        azure_user.save()
        # confirm user cannot log in
        try:
            self._do_get(c=c, url='/', expected_status_code=403, login_startswith=None)
        # if Django authentication backend is disabled, then NoReverseMatch is expected for the 'setup' pattern name
        # (since 2FA is not fully configured)
        except NoReverseMatch as err:
            self.assertIn('setup', str(err))
            # exception should only be raised if Django authentication backend is disabled
            self.assertFalse(has_django_auth_backend)
        # undo superuser change and reconfirm login is still possible
        azure_user.is_superuser = False
        azure_user.save()
        response = self._do_get(c=c, url='/', expected_status_code=200, login_startswith=None)
        self.assertNotIn(enable_2fa_txt, str(response.content))
        # change user so that they are inactive
        azure_user.is_active = False
        azure_user.save()
        # confirm user cannot log in
        self._do_get(
            c=c,
            url='/',
            expected_status_code=302,
            login_startswith=reverse('two_factor:{n}'.format(n=CONST_LOGIN_URL_NAME))
        )

    def check_callable_serving_static(self, user, path_kwargs, view_name, expected_callable, view_class):
        """ Checks that the expected method is called while serving a static file for download.

        Used to check how bulk import files, person photos and attachments are served for download in different
        configurations.

        :param user: User requesting to download static file.
        :param path_kwargs: Dictionary of keyword arguments that can be expanded to define the path where the file
        exists. Will be passed as a kwargs parameter in reverse(...).
        :param view_name: Name of view that will be passed as a parameter into reverse(...) to serve file download.
        :param expected_callable: Method that is expected to be called while serving the static file.
        :param view_class: Class of view that will render the response while serving the static file.
        :return: Nothing.
        """
        request = RequestFactory().get(reverse(view_name, kwargs=path_kwargs))
        # add callable to ensure 2FA verification passes
        setattr(user, 'is_verified', self.tautology)
        request.user = user
        with mock_patch(expected_callable) as mocked_callable:
            # instantiate view
            download_view = view_class.as_view()
            # get method for view is called
            download_view(request, **path_kwargs)
            # assert that expected method was called during handling of GET request
            mocked_callable.assert_called_once()

    def check_for_eula(self, fdp_user, response, url, expected_view):
        """ Checks that a user is first required to agree to a EULA before access a URL that requires it.

        :param fdp_user: User attempting to access URL.
        :param response: Http response object once user has been logged in. Contains "client" attribute for further
        tests.
        :param url: Url that user is attempting to access.
        :param expected_view: View that is expected to render the page that the user is accessing through the URL.
        :return: Nothing.
        """
        eula_txt = 'end user license agreement'
        all_kwargs = {'url': url, 'login_startswith': None}
        success_kwargs = {'expected_status_code': 200, **all_kwargs}
        forbidden_kwargs = {'expected_status_code': 403, **all_kwargs}
        # ensure that at start of check, user does not have any EULA agreement
        fdp_user.agreed_to_eula = None
        fdp_user.full_clean()
        fdp_user.save()
        with self.settings(FDP_EULA_SPLASH_ENABLE=False):
            self.assertFalse(AbstractConfiguration.eula_splash_enabled())
            response = self._do_get(c=response.client, **success_kwargs)
            self.assertNotIn(eula_txt, str(response.content))
            self._assert_class_based_view(response=response, expected_view=expected_view)
            logger.debug(f'With EULA disabled, and without agreeing to EULA, user can access: {url}')
        self.assertTrue(AbstractConfiguration.eula_splash_enabled())
        response = self._do_get(c=response.client, **forbidden_kwargs)
        self.assertIn(eula_txt, str(response.content))
        self.assertEqual(response.template_name, 'fdpuser/templates/eula_required.html')
        logger.debug(f'With EULA enabled, user must first agree to EULA before accessing: {url}')
        fdp_user.agreed_to_eula = now()
        fdp_user.full_clean()
        fdp_user.save()
        response = self._do_get(c=response.client, **success_kwargs)
        self.assertNotIn(eula_txt, str(response.content))
        self._assert_class_based_view(response=response, expected_view=expected_view)
        logger.debug(f'With EULA enabled, once agreeing to EULA, user can access: {url}')

    def exercise_federated_login_for_all(self):
        """ Tests that the federated login page works as expected using both local and Azure configuration settings.

        :return: Nothing.
        """
        urls_to_test = [
            # (is_url_admin, url),
            (False, reverse('profiles:command_search')),
            (False, reverse('fdpuser:settings')),
            (True, reverse('admin:index')),
            (True, reverse('admin:core_person_changelist')),
            (True, reverse('changing:index')),
            (True, reverse('changing:persons'))
        ]
        num_of_users = FdpUser.objects.all().count()
        federated_login_url = reverse('federated_login')
        admin_login_url = reverse('admin:login')
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            fdp_user = self._create_fdp_user(
                is_host=user_role.get(self._is_host_key, False),
                is_administrator=user_role.get(self._is_administrator_key, False),
                is_superuser=user_role.get(self._is_superuser_key, False),
                email_counter=i + num_of_users
            )
            if AbstractConfiguration.use_only_azure_active_directory():
                fdp_user.only_external_auth = True
                fdp_user.full_clean()
                fdp_user.save()
            user_label = user_role[self._label]
            # test for all URLs
            for url_tuple in urls_to_test:
                is_url_admin = url_tuple[0]
                url = url_tuple[1]
                # redirection for Django admin has two steps instead of one
                is_url_in_admin = url.startswith('/admin')
                login_startswith = federated_login_url if not is_url_in_admin else admin_login_url
                client = Client(**self._local_client_kwargs)
                client.logout()
                logger.debug(f'Checking that federated login appears for unauthenticated {user_label} for {url}')
                response = self._do_get(c=client, url=url, expected_status_code=302, login_startswith=login_startswith)
                if is_url_in_admin:
                    response = self._do_get(c=response.client, url=response.url, expected_status_code=302,
                                            login_startswith=federated_login_url)
                # skip for anonymous user
                if not user_role[self._is_anonymous_key]:
                    # only check URLs if they are non-admin or the user is an administrator/superuser
                    if user_role[self._is_administrator_key] or user_role[self._is_superuser_key] or not is_url_admin:
                        logger.debug(f'Checking that federated login does not appear for '
                                     f'authenticated {user_label} for {url}')
                        # cannot use default Django login
                        if AbstractConfiguration.use_only_azure_active_directory():
                            # super users cannot also be authenticated through Azure Active Directory
                            if fdp_user.is_superuser:
                                continue
                            response.client.force_login(user=fdp_user)
                            self.add_user_social_auth(azure_user=fdp_user)
                        # can use default Django login
                        else:
                            two_factor = self._create_2fa_record(user=fdp_user)
                            response = self._do_login(
                                c=response.client,
                                username=fdp_user.email,
                                password=self._password,
                                two_factor=two_factor,
                                login_status_code=200,
                                two_factor_status_code=200,
                                will_login_succeed=True
                            )
                        # check that URL loads without federated login
                        self._do_get(c=response.client, url=url, expected_status_code=200, login_startswith=None)
