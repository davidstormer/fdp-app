from django.test import TestCase, Client
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.util import random_hex
from django_otp.oath import totp
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse, reverse_lazy
from django.conf import settings
from django.apps import apps
from fdpuser.models import FdpUser
from .models import AbstractUrlValidator, AbstractConfiguration
from json import dumps


def local_test_settings_required(func):
    """ Retrieves a decorator method that allows tests to be skipped unless the necessary settings have been configured
    for a local development environment.

    :param func: Function that should be skipped unless the necessary settings are configured.
    :return: Decorator.
    """
    def decorator(*args, **kwargs):
        """ Decorator that allows tests to be skipped unless the necessary settings have been configured for a local
        development environment.

        :param args: Positional arguments for decorated test method.
        :param kwargs: Keyword arguments for decorated test method.
        :return: Nothing.
        """
        if AbstractConfiguration.is_using_local_configuration():
            func(*args, **kwargs)
        else:
            print('\nSkipped {t}. It requires local test settings and can be run with the command: {c}'.format(
                t=func.__name__, c='python manage.py test --settings=fdp.configuration.test.test_local_settings'))
    return decorator


def azure_test_settings_required(func):
    """ Retrieves a decorator method that allows tests to be skipped unless the necessary settings have been configured
    for a simulated Microsoft Azure hosting environment, including with authentication possible through BOTH Django
    and Azure Active Directory.

    :param func: Function that should be skipped unless the necessary settings are configured.
    :return: Decorator.
    """
    def decorator(*args, **kwargs):
        """ Decorator that allows tests to be skipped unless the necessary settings have been configured for a simulated
        Microsoft Azure hosting environment, including with authentication possible through BOTH Django and Azure
        Active Directory.

        :param args: Positional arguments for decorated test method.
        :param kwargs: Keyword arguments for decorated test method.
        :return: Nothing.
        """
        if AbstractConfiguration.is_using_azure_configuration() \
                and AbstractConfiguration.can_do_azure_active_directory() \
                and not AbstractConfiguration.use_only_azure_active_directory():
            func(*args, **kwargs)
        else:
            print('\nSkipped {t}. It requires Azure test settings and can be run with the command: {c}'.format(
                t=func.__name__, c='python manage.py test --settings=fdp.configuration.test.test_azure_settings'))
    return decorator


def azure_only_test_settings_required(func):
    """ Retrieves a decorator method that allows tests to be skipped unless the necessary settings have been configured
    for a simulated Microsoft Azure hosting environment, including with authentication possible ONLY through Azure
    Active Directory.

    :param func: Function that should be skipped unless the necessary settings are configured.
    :return: Decorator.
    """
    def decorator(*args, **kwargs):
        """ Decorator that allows tests to be skipped unless the necessary settings have been configured for a simulated
        Microsoft Azure hosting environment, including with authentication possible through ONLY Azure Active Directory.

        :param args: Positional arguments for decorated test method.
        :param kwargs: Keyword arguments for decorated test method.
        :return: Nothing.
        """
        if AbstractConfiguration.is_using_azure_configuration() \
                and AbstractConfiguration.can_do_azure_active_directory() \
                and AbstractConfiguration.use_only_azure_active_directory():
            func(*args, **kwargs)
        else:
            print(
                '\nSkipped {t}. It requires Azure only test settings and can be run with the command: {c}'.format(
                    t=func.__name__,
                    c='python manage.py test --settings=fdp.configuration.test.test_azure_only_settings'
                )
            )
    return decorator


class AbstractTestCase(TestCase):
    """ Abstract class from which TestCase classes can inherit.

    Provides reusable methods to log in with 2FA support.

    """
    #: Dictionary of keyword argument that can be expanded to initialize an instance of Django's Client(...) model.
    _local_client_kwargs = {'REMOTE_ADDR': '127.0.0.1'}

    #: Dictionary of keyword arguments that can be expanded to specify a guest administrator when creating a user.
    _guest_admin_dict = {'is_host': False, 'is_administrator': True, 'is_superuser': False}

    #: Dictionary of keyword arguments that can be expanded to specify a host administrator when creating a user.
    _host_admin_dict = {'is_host': True, 'is_administrator': True, 'is_superuser': False}

    #: Key indicating whether confidentiable object is restricted to administrator only or not.
    _for_admin_only_key = 'for_admin_only'

    #: Key indicating whether confidentiable object is restricted to host users only or not.
    _for_host_only_key = 'for_host_only'

    #: Key indicating unique name for confidentiable object.
    _name_key = 'name'

    #: Key indicating whether confidentiable object is restricted to a FDP organization only or not.
    _has_fdp_org_key = 'has_fdp_org'

    #: Key indicating unique primary key for confidentiable object.
    _pk_key = 'pk'

    #: Key indicating user-friendly label for user role.
    _label = 'label'

    #: Dictionary that can be expanded into keyword arguments to define a confidentiable record as unrestricted.
    _not_confidential_dict = {'for_admin_only': False, 'for_host_only': False}

    #: Dictionary that can be expanded into keyword arguments to define a person as a member of law enforcement.
    _is_law_dict = {'is_law_enforcement': True}

    #: List of permutations that a confidentiable object can take.
    _confidentials = [
        {
            _for_admin_only_key: False,
            _for_host_only_key: False,
            _name_key: 'UnrestrictedWithoutFdpOrg',
            _has_fdp_org_key: False,
            _label: 'Unrestricted without FDP Org'
        },
        {
            _for_admin_only_key: True,
            _for_host_only_key: False,
            _name_key: 'AdminOnlyWithoutFdpOrg',
            _has_fdp_org_key: False,
            _label: 'Admin only without FDP Org'
        },
        {
            _for_admin_only_key: False,
            _for_host_only_key: True,
            _name_key: 'HostOnlyWithoutFdpOrg',
            _has_fdp_org_key: False,
            _label: 'Host only without FDP Org'
        },
        {
            _for_admin_only_key: True,
            _for_host_only_key: True,
            _name_key: 'AdminOnlyHostOnlyWithoutFdpOrg',
            _has_fdp_org_key: False,
            _label: 'Admin only and host only without FDP Org'
        },
        {
            _for_admin_only_key: False,
            _for_host_only_key: False,
            _name_key: 'UnrestrictedWithFdpOrg',
            _has_fdp_org_key: True,
            _label: 'Unrestricted with FDP Org'
        },
        {
            _for_admin_only_key: True,
            _for_host_only_key: False,
            _name_key: 'AdminOnlyWithFdpOrg',
            _has_fdp_org_key: True,
            _label: 'Admin only with FDP Org'
        },
        {
            _for_admin_only_key: False,
            _for_host_only_key: True,
            _name_key: 'HostOnlyWithFdpOrg',
            _has_fdp_org_key: True,
            _label: 'Host only with FDP Org'
        },
        {
            _for_admin_only_key: True,
            _for_host_only_key: True,
            _name_key: 'AdminOnlyHostOnlyWithFdpOrg',
            _has_fdp_org_key: True,
            _label: 'Admin only and host only with FDP Org'
        }
    ]

    #: Key used to indicate in environment variables whether RECAPTCHA is in test mode or not.
    _recaptcha = 'RECAPTCHA_TESTING'

    #: Key indicating whether FDP user is anonymous or authenticated.
    _is_anonymous_key = 'is_anonymous'

    #: Key indicating whether FDP user is host or guest.
    _is_host_key = 'is_host'

    #: Key indicating whether FDP user is administrator or staff.
    _is_administrator_key = 'is_administrator'

    #: Key indicating whether FDP user is super user or not.
    _is_superuser_key = 'is_superuser'

    #: Key indicating url for view.
    _url_key = 'url'

    #: Key indicating namespace and viewname to pass into reverse(...) to generate url for view.
    _url_reverse_viewname_key = 'url_reverse_viewname'

    #: Key indicating primary key parameter name to pass in as a keyword argument to reverse(...) to generate url for
    # view.
    _url_reverse_kwargs_pk_key = 'url_reverse_kwargs_pk'

    #: Key indicating whether anonymous users can access view.
    _is_anonymous_accessible_key = 'is_anonymous_accessible'

    #: Key indicating whether staff users can access view.
    _is_staff_accessible_key = 'is_staff_accessible'

    #: Key indicating whether administrator users can access view.
    _is_admin_accessible_key = 'is_admin_accessible'

    #: Password used for users that are created.
    _password = 'AdminAdminAdmin'

    #: HTML attributes expected if login view is rendered with the 2FA token verification step.
    _token_step_attributes = 'name="login_view-current_step" value="token"'

    #: HTML attributes expected if login view is rendered with the username and password verification step.
    _username_password_step_attributes = 'name="login_view-current_step" value="auth"'

    #: Different user roles for FDP and their corresponding properties
    _user_roles = [
        {
            _is_anonymous_key: True,
            _label: _('Anonymous User')
        },
        {
            _is_anonymous_key: False,
            _is_host_key: False,
            _is_administrator_key: False,
            _is_superuser_key: False,
            _label: _('Guest Staff')
        },
        {
            _is_anonymous_key: False,
            _is_host_key: True,
            _is_administrator_key: False,
            _is_superuser_key: False,
            _label: _('Host Staff')
        },
        {
            _is_anonymous_key: False,
            _is_host_key: False,
            _is_administrator_key: True,
            _is_superuser_key: False,
            _label: _('Guest Administrator')
        },
        {
            _is_anonymous_key: False,
            _is_host_key: True,
            _is_administrator_key: True,
            _is_superuser_key: False,
            _label: _('Host Administrator')
        },
        {
            _is_anonymous_key: False,
            _is_host_key: False,
            _is_administrator_key: False,
            _is_superuser_key: True,
            _label: _('Super User')
        }
    ]

    #: Default primary key used as a keyword argument in the reverse(...) method to generate URLs for profile views.
    _default_pk = 0

    #: Different views in FDP that can be tested for access
    _views = [
        {
            _url_key: reverse('profiles:officer_search'),
            _label: _('Officer Search'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse('profiles:officer_search_results'),
            _label: _('Officer Search Results'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_reverse_viewname_key: 'profiles:officer',
            _url_reverse_kwargs_pk_key: 'pk',
            _url_key: None,  # build url based on primary key for officer
            _label: _('Officer Profile'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_reverse_viewname_key: 'profiles:officer_download_all_files',
            _url_reverse_kwargs_pk_key: 'pk',
            _url_key: None,  # build url based on primary key for officer
            _label: _('Download All Officer Files'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse('admin:index'),
            _label: _('Admin Index'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: False,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse('fdpuser:settings'),
            _label: _('FDP User Settings'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse_lazy('fdpuser:confirm_password_change'),
            _label: _('Confirm Password Change'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse('fdpuser:confirm_2fa_reset'),
            _label: _('Confirm 2FA Reset'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse('fdpuser:change_password'),
            _label: _('Do Password Change'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse_lazy('password_reset'),
            _label: _('Do Password Reset'),
            _is_anonymous_accessible_key: True,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse('fdpuser:reset_2fa'),
            _label: _('Do 2FA Reset'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
        {
            _url_key: reverse('two_factor:profile'),
            _label: _('2FA Profile'),
            _is_anonymous_accessible_key: False,
            _is_staff_accessible_key: True,
            _is_admin_accessible_key: True
        },
    ]

    def setUp(self):
        """ Ensures that automated tests are skipped unless configuration is set to local development environment.

        :return: Nothing.
        """
        # automated tests will be skipped unless configuration is for local development or simulating a host environment
        if not (settings.USE_LOCAL_SETTINGS or getattr(settings, 'USE_TEST_AZURE_SETTINGS', False)):
            print(_('\nSkipping tests in {t}'.format(t=self.__class__.__name__)))
            self.skipTest(reason=_('Automated tests will only run in a local development environment'))
        # configuration is for local development
        super().setUp()

    def _assert_2fa_step_in_login_view(self, response, expected_view):
        """ Asserts that the 2FA step is rendered in the login view.

        :param response: Http response to check.
        :param expected_view: Class for view that is expected.
        :return: Nothing.
        """
        self.assertIn(self._token_step_attributes, str(response.content))
        self._assert_class_based_view(response=response, expected_view=expected_view)

    def _assert_username_and_password_step_in_login_view(self, response, expected_view):
        """ Asserts that the username/password step is rendered in the login view.

        :param response: Http response to check.
        :param expected_view: Class for view that is expected.
        :return: Nothing.
        """
        response_content = str(response.content)
        self.assertIn(self._username_password_step_attributes, response_content)
        self.assertNotIn(self._token_step_attributes, response_content)
        self._assert_class_based_view(response=response, expected_view=expected_view)

    @staticmethod
    def __get_file_path_for_view(instance, field_with_file, base_url):
        """ Retrieves the file path from instance, so that it can be passed as a parameter and processed through a
        download view.

        :param instance: Instance that has the file as an attribute.
        :param field_with_file: Name of attribute storing the file.
        :param base_url: Base URL through which file is served for download.
        :return: File path that can be passed as a parameter into a download view.
        """
        file_path = str(getattr(instance, field_with_file))
        if file_path.startswith(base_url):
            file_path = file_path[len(base_url):]
        return file_path

    def _add_fdp_import_file(self):
        """ Creates a bulk import file in the database, and adds a reference to it through the
        '_fdp_import_file' attribute.

        :return: Nothing.
        """
        # loads the model dynamically
        fdp_import_file_model = apps.get_model('bulk', 'FdpImportFile')
        # number of import files that exist already
        num_of_import_files = fdp_import_file_model.objects.all().count()
        # create the file in the database with a unique name
        self._fdp_import_file = fdp_import_file_model.objects.create(
            file='{b}x{i}.csv'.format(
                b=AbstractUrlValidator.DATA_WIZARD_IMPORT_BASE_URL,
                i=num_of_import_files + 1
            )
        )

    def _get_fdp_import_file_file_path_for_view(self):
        """ Retrieves the file path of a bulk import file, so that it can be passed as a parameter and processed
        through a view.

        Uses the '_fdp_import_file' attribute that is added through the _add_fdp_import_file(...) method.

        :return: File path that can be passed as a parameter into a view to download the bulk import file.
        """
        return self.__get_file_path_for_view(
            instance=self._fdp_import_file,
            field_with_file='file',
            base_url=AbstractUrlValidator.DATA_WIZARD_IMPORT_BASE_URL
        )

    def _add_person_photo(self):
        """ Creates a person photo in the database, and adds a reference to it through the '_person_photo' attribute.

        :return: Nothing.
        """
        # loads the model dynamically and adds person
        person_model = apps.get_model('core', 'Person')
        person = person_model.objects.create(name='Unnamed', **self._is_law_dict)
        # loads the model dynamically
        person_photo_model = apps.get_model('core', 'PersonPhoto')
        # number of import files that exist already
        num_of_person_photos = person_photo_model.objects.all().count()
        # create the person photo file in the database with a unique name
        self._person_photo = person_photo_model.objects.create(
            person=person,
            photo='{b}x{i}.png'.format(b=AbstractUrlValidator.PERSON_PHOTO_BASE_URL, i=num_of_person_photos + 1)
        )

    def _get_person_photo_file_path_for_view(self):
        """ Retrieves the file path of a person photo file, so that it can be passed as a parameter and processed
        through a view.

        Uses the '_person_photo' attribute that is added through the _add_person_photo(...) method.

        :return: File path that can be passed as a parameter into a view to download the person photo file.
        """
        return self.__get_file_path_for_view(
            instance=self._person_photo,
            field_with_file='photo',
            base_url=AbstractUrlValidator.PERSON_PHOTO_BASE_URL
        )

    def _add_attachment(self):
        """ Creates an attachment in the database, and adds a reference to it through the '_attachment' attribute.

        :return: Nothing.
        """
        # loads the model dynamically
        attachment_model = apps.get_model('sourcing', 'Attachment')
        # number of attachments that exist already
        num_of_attachments = attachment_model.objects.all().count()
        # create the attachment in the database with a unique name
        self._attachment = attachment_model.objects.create(
            file='{b}x{i}.txt'.format(b=AbstractUrlValidator.ATTACHMENT_BASE_URL, i=num_of_attachments + 1),
            name='Unnamed'
        )

    def _get_attachment_file_path_for_view(self):
        """ Retrieves the file path of an attachment, so that it can be passed as a parameter and processed
        through a view.

        Uses the '_attachment' attribute that is added through the _add_attachment(...) method.

        :return: File path that can be passed as a parameter into a view to download the attachment file.
        """
        return self.__get_file_path_for_view(
            instance=self._attachment,
            field_with_file='file',
            base_url=AbstractUrlValidator.ATTACHMENT_BASE_URL
        )

    def _create_fdp_user(self, is_host, is_administrator, is_superuser, password=None, email=None, email_counter=None):
        """ Create a FDP user in the test database.

        :param password: Password to use for the FDP user. Omit to use default.
        :param is_host: True if FDP user is a host, false if it is a guest.
        :param is_administrator: True if FDP user is an administrator, false otherwise.
        :param is_superuser: True if FDP user is a super user, false otherwise.
        :param email: Email address for the FDP user. Omit to use default.
        :param email_counter: Counter index to used to create unique email addresses. Will be ignored if email is
        defined.
        :return: FDP user created in the test database.
        """
        if password is None:
            password = self._password
        if email is None:
            if email_counter is None:
                email = 'donotreply@google.com'
            else:
                email = 'donotreply{i}@google.com'.format(i=email_counter)
        fdp_user = FdpUser.objects.create_user(
            email=email,
            password=password,
            is_host=is_host,
            is_administrator=is_administrator,
            is_superuser=is_superuser
        )
        fdp_user.full_clean()
        fdp_user.save()
        self.assertTrue(
            FdpUser.objects.filter(
                pk=fdp_user.pk, is_host=is_host, is_administrator=is_administrator, is_superuser=is_superuser
            ).exists()
        )
        self.assertTrue((FdpUser.objects.get(pk=fdp_user.pk)).is_active)
        return fdp_user

    def _do_2fa(self, c, token, expected_status_code, expected_path_info):
        """ Perform a 2FA verification for a user.

        :param c: Instantiated client object used to perform 2FA verification.
        :param token: Token to use in 2FA verification.
        :param expected_status_code: Expected HTTP status code returned by login attempt.
        :param expected_path_info: Expected value for HttpRequest object's PATH_INFO.
        :return: Response returned by 2FA verification.
        """
        response = c.post(
            reverse(settings.LOGIN_URL),
            {
                'login_view-current_step': 'token',
                'token-otp_token': token
            },
            follow=True
        )
        self.assertEqual(response.status_code, expected_status_code)
        self.assertEqual(response.request['PATH_INFO'], expected_path_info)
        return response

    def _create_2fa_record(self, user):
        """ Creates a record to verify 2FA for a particular user.

        :param user: User for which to create record.
        :return: Returns 2FA verifying record.
        """
        key = random_hex()
        totp_device = user.totpdevice_set.create(name='default', key=key)
        self.assertTrue(TOTPDevice.objects.filter(pk=totp_device.pk, key=key).exists())
        return totp_device

    def _do_django_username_password_authentication(
            self, c, username, password, login_status_code, override_login_url=None
    ):
        """ Performs authentication with a username and password combination through the Django authentication backend.

        :param c: Instantiated client object used to perform authentication.
        :param username: Username for authentication attempt.
        :param password: Password for authentication attempt.
        :param override_login_url: An optional relative path to which the request containing the Django username and
        password should be submitted. Will be ignored if None.
        :return: Response returned by authentication attempt.
        """
        response = c.post(
            reverse(settings.LOGIN_URL) if not override_login_url else override_login_url,
            {'auth-username': username, 'auth-password': password, 'login_view-current_step': 'auth'},
            follow=True
        )
        self.assertEqual(response.status_code, login_status_code)
        return response

    def _do_login(
            self, c, username, password, two_factor, login_status_code, two_factor_status_code, will_login_succeed
    ):
        """ Perform a login attempt.

        :param c: Instantiated client object used to perform login attempt.
        :param username: Username used during login attempt.
        :param password: Password used during login attempt.
        :param two_factor: 2FA verified record for user.
        :param login_status_code: Expected HTTP status code returned by login attempt.
        :param two_factor_status_code: Expected HTTP status code returned by 2FA verification attempt.
        :param will_login_succeed: True if login is expected to succeed, false otherwise.
        :return: Response returned by login attempt or 2FA verification attempt.
        """
        response = self._do_django_username_password_authentication(
            c=c,
            username=username,
            password=password,
            login_status_code=login_status_code
        )
        if login_status_code == 200:
            if two_factor_status_code is not None and two_factor is not None:
                response = self._do_2fa(
                    c=response.client,
                    token=totp(two_factor.bin_key),
                    expected_status_code=two_factor_status_code,
                    expected_path_info=reverse('profiles:index') if will_login_succeed
                    else reverse(settings.LOGIN_URL)
                )
            user = response.context['user']
            self.assertEqual(user.is_authenticated, will_login_succeed)
        return response

    def _do_get(self, c, url, expected_status_code, login_startswith):
        """ Use GET method to access a particular URL.

        :param c: Instantiated client object used to access a particular URL.
        :param url: URL to access with GET method.
        :param expected_status_code: Expected HTTP status code returned by GET access.
        :param login_startswith: Specify what the redirected login URL will start with.
        :return: Response returned by GET access.
        """
        response = c.get(url)
        self.assertEqual(response.status_code, expected_status_code)
        # if redirecting, ensure that redirecting to login view
        if expected_status_code == 302:
            self.assertTrue(str(response.url).startswith(login_startswith))
        return response

    def _do_post(self, c, url, data, expected_status_code, login_startswith):
        """ Use POST method to submit data.

        :param c: Instantiated client object used to submit data.
        :param url: URL to which data is submitted with POST method.
        :param data: Data submitted with POST method.
        :param expected_status_code: Expected HTTP status code returned by POST access.
        :param login_startswith: Specify what the redirected login URL will start with.
        :return: Response returned by POST access.
        """
        response = c.post(url, data)
        self.assertEqual(response.status_code, expected_status_code)
        # if redirecting, ensure that redirecting to login view
        if expected_status_code == 302:
            self.assertTrue(str(response.url).startswith(login_startswith))
        return response

    def _do_async_post(self, c, url, data, expected_status_code, login_startswith):
        """ Use asynchronous POST method to submit JSON data.

        :param c: Instantiated client object used to submit JSON data.
        :param url: URL to which data is submitted with asynchronous POST request.
        :param data: JSON data submitted with asynchronous POST request.
        :param expected_status_code: Expected HTTP status code returned by asynchronous POST request.
        :param login_startswith: Specify what the redirected login URL will start with.
        :return: Response returned by asynchronous POST request.
        """
        response = c.post(url, str(dumps(data)), content_type='application/json')
        self.assertEqual(response.status_code, expected_status_code)
        # if redirecting, ensure that redirecting to login view
        if expected_status_code == 302:
            self.assertTrue(str(response.url).startswith(login_startswith))
        return response

    def _get_response_from_get_request(self, fdp_user, url, expected_status_code, login_startswith):
        """ Retrieves an HTTP response after sending an HTTP request through a GET method to a particular view for
        an FDP user.

        :param fdp_user: FDP user for which to send HTTP request through a GET method.
        :param url: Url to which to send HTTP request throuhg a GET method.
        :param expected_status_code: Expected HTTP status code that is returned in the response.
        :param login_startswith: Url to which response may be redirected. Only used when HTTP status code is 302.
        :return: String representation of the HTTP response.
        """
        client = Client(**self._local_client_kwargs)
        client.logout()
        two_factor = self._create_2fa_record(user=fdp_user)
        response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        response = self._do_get(
            c=response.client,
            url=url,
            expected_status_code=expected_status_code,
            login_startswith=login_startswith
        )
        return str(response.content)

    @staticmethod
    def _can_user_access_data(for_admin_only, for_host_only, has_fdp_org, fdp_user, fdp_org):
        """ Checks whether a user can access data with particular confidentiality levels.

        :param for_admin_only: True if the data is restricted to administrators only, false otherwise.
        :param for_host_only: True if the data is restricted to users belonging to a host organization only, false
        otherwise.
        :param has_fdp_org: True if the data is restricted to a particular organization, false otherwise.
        :param fdp_user: User attempting to access data.
        :param fdp_org: FDP organization to which data is restricted.
        :return: True if user can access data with particular confidentiality levels, false otherwise.
        """
        # DATA NOT RESTRICTED FOR ADMINS OR (USER IS ADMIN OR SUPERUSER)
        # AND
        # DATA IS NOT RESTRICTED TO HOSTS OR USER IS HOST OR USER IS SUPERUSER
        # AND
        # DATA IS NOT FDP ORG RESTRICTED OR ORG MATCHES OR USER IS SUPERUSER OR USER IS ADMIN & HOST
        return (
                (not for_admin_only) or (for_admin_only and (fdp_user.is_administrator or fdp_user.is_superuser))
            ) and (
                (not for_host_only) or (for_host_only and (fdp_user.is_host or fdp_user.is_superuser))
            ) and (
                (not has_fdp_org) or (
                    has_fdp_org and (
                        fdp_user.is_superuser or (
                            fdp_user.is_administrator and fdp_user.is_host
                        ) or fdp_org == fdp_user.fdp_organization
                    )
                )
            )

    def _check_if_data_appears(self, text_for_data, content, fdp_org, fdp_user):
        """ Check if a row of data with different confidentiality levels appear in some content.

        Can be used to test if confidentiable data is appearing in views.

        :param text_for_data: Text representing data that will be output in the console window as the test is run.
        :param content: Content in which data may or may not appear.
        :param fdp_org: FDP Organization that may be assigned to the data.
        :param fdp_user: FDP user accessing the data.
        :return: Nothing.
        """
        # ensure that content (e.g. response from a view access) is in string format
        str_content = str(content)
        # cycle through all permutations of confidentiality for the row for data
        for confidential in self._confidentials:
            should_data_appear = self._can_user_access_data(
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key],
                has_fdp_org=confidential[self._has_fdp_org_key],
                fdp_user=fdp_user,
                fdp_org=fdp_org
            )
            if should_data_appear:
                self.assertIn(confidential[self._name_key], str_content)
            else:
                self.assertNotIn(confidential[self._name_key], str_content)
            print(
                _('{t} is successful ({d} {a})'.format(
                    t=confidential[self._label],
                    d=text_for_data,
                    a=_('does not appear') if not should_data_appear else _('appears')
                ))
            )

    def _check_that_data_does_not_appear(self, text_for_data, content):
        """ Check that a row of data with different confidentiality levels never appears in some content.

        Can be used to test if confidentiable data is always excluded from a view.

        :param text_for_data: Text representing data that will be output in the console window as the test is run.
        :param content: Content in which data may or may not appear.
        :return: Nothing.
        """
        # ensure that content (e.g. response from a view access) is in string format
        str_content = str(content)
        # cycle through all permutations of confidentiality for the row for data
        for confidential in self._confidentials:
            self.assertNotIn(confidential[self._name_key], str_content)
            print(
                _(
                    '{t} is successful ({d} {a})'.format(
                        t=confidential[self._label],
                        d=text_for_data,
                        a=_('does not appear')
                    )
                )
            )

    @staticmethod
    def _can_user_access_admin(fdp_user):
        """ Checks whether a user an access the admin portion of the site.

        :param fdp_user: FDP user for which to check access.
        :return: True if FDP user can access admin portion, false otherwise.
        """
        return fdp_user.is_administrator or fdp_user.is_superuser

    @staticmethod
    def _get_secondary_name(original_name):
        """ Retrieves a secondary name for a row of data.

        Removes the first two characters from the original name and replaces them with QQ.

        Used if confidential data is crossed with the same confidential data, e.g. when creating person relationships.

        :param original_name: Original name in confidential data.
        :return: Secondary name for row of data.
        """
        return '{s}{p}'.format(s='QQ', p=original_name[2:])

    def _check_admin_change_list_views(
            self, models_to_test, fdp_user, fdp_org, password, related_text, models_where_data_never_appears
    ):
        """ Check the different Admin Changelist views for a FDP user.

        :param models_to_test: List of models for which to test Admin Changelist views.
        :param fdp_user: FDP user accessing Admin Changelist views.
        :param fdp_org: FDP organization that may be added to the data.
        :param password: Password for FDP user.
        :param related_text: User-friendly text indicating reason that model is being tested, e.g. person.
        :param models_where_data_never_appears: List of models where the data never appears.
        :return: Nothing.
        """
        # cycle through all models that reference directly/indirectly
        for model_tuple in models_to_test:
            model_to_test = model_tuple[0]
            change_list_url = reverse(
                'admin:{app}_{model_to_test}_changelist'.format(
                    app=model_to_test._meta.app_label,
                    model_to_test=model_to_test._meta.model_name
                )
            )
            client = Client(**self._local_client_kwargs)
            client.logout()
            two_factor = self._create_2fa_record(user=fdp_user)
            # log in user
            response = self._do_login(
                c=client,
                username=fdp_user.email,
                password=password,
                two_factor=two_factor,
                login_status_code=200,
                two_factor_status_code=200,
                will_login_succeed=True
            )
            # navigate to changelist in admin
            can_user_access_admin = self._can_user_access_admin(fdp_user=fdp_user)
            response = self._do_get(
                c=response.client,
                url=change_list_url,
                expected_status_code=200 if can_user_access_admin else 302,
                login_startswith=None if can_user_access_admin else reverse('admin:login')
            )
            # only if user can access the admin site
            if can_user_access_admin:
                text_for_data = _('{r} for {m}'.format(r=related_text, m=model_to_test._meta.model_name))
                content = response.content
                # if model is one that is not expected to appear
                if model_to_test in models_where_data_never_appears:
                    self._check_that_data_does_not_appear(text_for_data=text_for_data, content=content)
                # all other models
                else:
                    # check if the different permutations of confidentiality appear
                    self._check_if_data_appears(
                        text_for_data=text_for_data, content=content, fdp_org=fdp_org, fdp_user=fdp_user
                    )
            else:
                print(
                    _(
                        'Check for {m} is successful (user was redirected to login screen)'.format(
                            m=model_to_test._meta.model_name
                        )
                    )
                )

    def _check_admin_create_instance_views(
            self, models_to_test, fdp_user, fdp_org, password, related_text, models_where_data_never_appears
    ):
        """ Check the different Admin create instance views for a FDP user.

        :param models_to_test: List of models for which to test Admin create instance views.
        :param fdp_user: FDP user accessing Admin create instance views.
        :param fdp_org: FDP organization that may be added to the data.
        :param password: Password for FDP user.
        :param related_text: User-friendly text indicating reason that model is being tested, e.g. person.
        :param models_where_data_never_appears: List of models where the data never appears.
        :return: Nothing.
        """
        # cycle through all models that reference directly/indirectly
        for model_tuple in models_to_test:
            model_to_test = model_tuple[0]
            change_list_url = reverse(
                'admin:{app}_{model_to_test}_add'.format(
                    app=model_to_test._meta.app_label,
                    model_to_test=model_to_test._meta.model_name
                )
            )
            client = Client(**self._local_client_kwargs)
            client.logout()
            two_factor = self._create_2fa_record(user=fdp_user)
            # log in user
            response = self._do_login(
                c=client,
                username=fdp_user.email,
                password=password,
                two_factor=two_factor,
                login_status_code=200,
                two_factor_status_code=200,
                will_login_succeed=True
            )
            # navigate to create instance in admin
            can_user_access_admin = self._can_user_access_admin(fdp_user=fdp_user)
            response = self._do_get(
                c=response.client,
                url=change_list_url,
                expected_status_code=200 if can_user_access_admin else 302,
                login_startswith=None if can_user_access_admin else reverse('admin:login')
            )
            # only if user can access the admin site
            if can_user_access_admin:
                text_for_data = _('{r} for {m}'.format(r=related_text, m=model_to_test._meta.model_name))
                content = response.content
                # if model is one that is not expected to appear
                if model_to_test in models_where_data_never_appears:
                    self._check_that_data_does_not_appear(text_for_data=text_for_data, content=content)
                # all other models
                else:
                    # check if the different permutations of confidentiality appear
                    self._check_if_data_appears(
                        text_for_data=text_for_data, content=content, fdp_org=fdp_org, fdp_user=fdp_user
                    )
            else:
                print(
                    _(
                        'Check for {m} is successful (user was redirected to login screen)'.format(
                            m=model_to_test._meta.model_name
                        )
                    )
                )

    def _check_admin_change_instance_views(
            self, models_to_test, fdp_user, fdp_org, password, related_text, models_where_data_never_appears
    ):
        """ Check the different Admin change instance views for a FDP user.

        :param models_to_test: List of models for which to test Admin change instance views.
        :param fdp_user: FDP user accessing Admin change instance views.
        :param fdp_org: FDP organization that may be added to the data.
        :param password: Password for FDP user.
        :param related_text: User-friendly text indicating reason that model is being tested, e.g. person.
        :param models_where_data_never_appears: List of models where the data never appears.
        :return: Nothing.
        """
        # cycle through all models that reference directly/indirectly
        for model_tuple in models_to_test:
            model_to_test = model_tuple[0]
            model_pk = model_tuple[2]
            if model_pk is None:
                continue
            change_list_url = reverse(
                'admin:{app}_{model_to_test}_change'.format(
                    app=model_to_test._meta.app_label,
                    model_to_test=model_to_test._meta.model_name
                ),
                args=(model_pk,)
            )
            client = Client(**self._local_client_kwargs)
            client.logout()
            two_factor = self._create_2fa_record(user=fdp_user)
            # log in user
            response = self._do_login(
                c=client,
                username=fdp_user.email,
                password=password,
                two_factor=two_factor,
                login_status_code=200,
                two_factor_status_code=200,
                will_login_succeed=True
            )
            # navigate to create instance in admin
            can_user_access_admin = self._can_user_access_admin(fdp_user=fdp_user)
            response = self._do_get(
                c=response.client,
                url=change_list_url,
                expected_status_code=200 if can_user_access_admin else 302,
                login_startswith=None if can_user_access_admin else reverse('admin:login')
            )
            # only if user can access the admin site
            if can_user_access_admin:
                text_for_data = _('{r} for {m}'.format(r=related_text, m=model_to_test._meta.model_name))
                content = response.content
                # if model is one that is not expected to appear
                if model_to_test in models_where_data_never_appears:
                    self._check_that_data_does_not_appear(text_for_data=text_for_data, content=content)
                # all other models
                else:
                    # check if the different permutations of confidentiality appear
                    self._check_if_data_appears(
                        text_for_data=text_for_data, content=content, fdp_org=fdp_org, fdp_user=fdp_user
                    )
            else:
                print(
                    _(
                        'Check for {m} is successful (user was redirected to login screen)'.format(
                            m=model_to_test._meta.model_name
                        )
                    )
                )

    def _load_admin_change_instance_views(self, models_to_test, fdp_user, fdp_org, password, related_text):
        """ Load the different Admin change instance views for a FDP user.

        :param models_to_test: List of models for which to test Admin change instance views.
        :param fdp_user: FDP user accessing Admin change instance views.
        :param fdp_org: FDP organization that may be added to the data.
        :param password: Password for FDP user.
        :param related_text: User-friendly text indicating reason that model is being tested, e.g. person.
        :return: Nothing.
        """
        # cycle through all models that reference directly/indirectly
        for model_tuple in models_to_test:
            model_to_test = model_tuple[0]
            model_pks = model_tuple[1]
            # cycle through all permutations of confidentiality for the row for data
            for confidential in self._confidentials:
                model_pk = model_pks[confidential[self._name_key]]
                change_list_url = reverse(
                    'admin:{app}_{model_to_test}_change'.format(
                        app=model_to_test._meta.app_label,
                        model_to_test=model_to_test._meta.model_name
                    ),
                    args=(model_pk,)
                )
                should_data_appear = self._can_user_access_data(
                    for_admin_only=confidential[self._for_admin_only_key],
                    for_host_only=confidential[self._for_host_only_key],
                    has_fdp_org=confidential[self._has_fdp_org_key],
                    fdp_user=fdp_user,
                    fdp_org=fdp_org
                )
                client = Client(**self._local_client_kwargs)
                client.logout()
                two_factor = self._create_2fa_record(user=fdp_user)
                # log in user
                response = self._do_login(
                    c=client,
                    username=fdp_user.email,
                    password=password,
                    two_factor=two_factor,
                    login_status_code=200,
                    two_factor_status_code=200,
                    will_login_succeed=True
                )
                # navigate to change instance in admin
                can_user_access_admin = self._can_user_access_admin(fdp_user=fdp_user)
                if not can_user_access_admin:
                    expected_status_code = 302
                    login_startswith = reverse('admin:login')
                elif can_user_access_admin and not should_data_appear:
                    # models that are directly Confidentiable or linked to Confidentiable data
                    expected_status_code = 302
                    login_startswith = reverse('admin:index')
                else:
                    expected_status_code = 200
                    login_startswith = None
                self._do_get(
                    c=response.client,
                    url=change_list_url,
                    expected_status_code=expected_status_code,
                    login_startswith=login_startswith
                )
                # only if user can access the admin site
                if can_user_access_admin:
                    text_for_data = _('{r} for {m}'.format(r=related_text, m=model_to_test._meta.model_name))
                    print(
                        _('{t} is successful ({d} {a})'.format(
                            t=confidential[self._label],
                            d=text_for_data,
                            a=_('does not appear') if not should_data_appear else _('appears')
                        ))
                    )
                else:
                    print(
                        _(
                            'Check for {m} is successful (user was redirected to login screen)'.format(
                                m=model_to_test._meta.model_name
                            )
                        )
                    )

    def _load_admin_history_views(self, models_to_test, fdp_user, fdp_org, password, related_text):
        """ Load the different Admin history views for a FDP user.

        :param models_to_test: List of models for which to test Admin history views.
        :param fdp_user: FDP user accessing Admin history views.
        :param fdp_org: FDP organization that may be added to the data.
        :param password: Password for FDP user.
        :param related_text: User-friendly text indicating reason that model is being tested, e.g. person.
        :return: Nothing.
        """
        # cycle through all models that reference directly/indirectly
        for model_tuple in models_to_test:
            model_to_test = model_tuple[0]
            model_pks = model_tuple[1]
            # cycle through all permutations of confidentiality for the row for data
            for confidential in self._confidentials:
                model_pk = model_pks[confidential[self._name_key]]
                change_list_url = reverse(
                    'admin:{app}_{model_to_test}_history'.format(
                        app=model_to_test._meta.app_label,
                        model_to_test=model_to_test._meta.model_name
                    ),
                    args=(model_pk,)
                )
                should_data_appear = self._can_user_access_data(
                    for_admin_only=confidential[self._for_admin_only_key],
                    for_host_only=confidential[self._for_host_only_key],
                    has_fdp_org=confidential[self._has_fdp_org_key],
                    fdp_user=fdp_user,
                    fdp_org=fdp_org
                )
                client = Client(**self._local_client_kwargs)
                client.logout()
                two_factor = self._create_2fa_record(user=fdp_user)
                # log in user
                response = self._do_login(
                    c=client,
                    username=fdp_user.email,
                    password=password,
                    two_factor=two_factor,
                    login_status_code=200,
                    two_factor_status_code=200,
                    will_login_succeed=True
                )
                # navigate to history in admin
                can_user_access_admin = self._can_user_access_admin(fdp_user=fdp_user)
                # user cannot access admin
                if not can_user_access_admin:
                    expected_status_code = 302
                    login_startswith = reverse('admin:login')
                # user can access admin
                else:
                    # only host administrators and super users can load admin history views
                    if fdp_user.is_superuser or (fdp_user.is_host and fdp_user.is_administrator):
                        # data not expected to appear
                        if not should_data_appear:
                            # models that are directly Confidentiable or linked to Confidentiable data
                            expected_status_code = 302
                            login_startswith = reverse('admin:index')
                        # data expected to appear
                        else:
                            expected_status_code = 200
                            login_startswith = None
                    # guest administrator cannot load admin history views
                    else:
                        expected_status_code = 403
                        login_startswith = None
                self._do_get(
                    c=response.client,
                    url=change_list_url,
                    expected_status_code=expected_status_code,
                    login_startswith=login_startswith
                )
                # only if user can access the admin site
                if can_user_access_admin:
                    text_for_data = _('{r} for {m}'.format(r=related_text, m=model_to_test._meta.model_name))
                    # user encountered 403 HTTP status code
                    if expected_status_code == 403:
                        print(
                            _('{t} is successful ({r})'.format(t=confidential[self._label], r=_('403 status code')))
                        )
                    # user can access page
                    else:
                        print(
                            _('{t} is successful ({d} {a})'.format(
                                t=confidential[self._label],
                                d=text_for_data,
                                a=_('does not appear') if not should_data_appear else _('appears')
                            ))
                        )
                else:
                    print(
                        _(
                            'Check for {m} is successful (user was redirected to login screen)'.format(
                                m=model_to_test._meta.model_name
                            )
                        )
                    )

    def _load_admin_delete_views(self, models_to_test, fdp_user, fdp_org, password, related_text):
        """ Load the different Admin delete views for a FDP user.

        :param models_to_test: List of models for which to test Admin delete views.
        :param fdp_user: FDP user accessing Admin delete views.
        :param fdp_org: FDP organization that may be added to the data.
        :param password: Password for FDP user.
        :param related_text: User-friendly text indicating reason that model is being tested, e.g. person.
        :return: Nothing.
        """
        # cycle through all models that reference directly/indirectly
        for model_tuple in models_to_test:
            model_to_test = model_tuple[0]
            model_pks = model_tuple[1]
            # cycle through all permutations of confidentiality for the row for data
            for confidential in self._confidentials:
                model_pk = model_pks[confidential[self._name_key]]
                change_list_url = reverse(
                    'admin:{app}_{model_to_test}_delete'.format(
                        app=model_to_test._meta.app_label,
                        model_to_test=model_to_test._meta.model_name
                    ),
                    args=(model_pk,)
                )
                should_data_appear = self._can_user_access_data(
                    for_admin_only=confidential[self._for_admin_only_key],
                    for_host_only=confidential[self._for_host_only_key],
                    has_fdp_org=confidential[self._has_fdp_org_key],
                    fdp_user=fdp_user,
                    fdp_org=fdp_org
                )
                client = Client(**self._local_client_kwargs)
                client.logout()
                two_factor = self._create_2fa_record(user=fdp_user)
                # log in user
                response = self._do_login(
                    c=client,
                    username=fdp_user.email,
                    password=password,
                    two_factor=two_factor,
                    login_status_code=200,
                    two_factor_status_code=200,
                    will_login_succeed=True
                )
                # navigate to delete in admin
                can_user_access_admin = self._can_user_access_admin(fdp_user=fdp_user)
                if not can_user_access_admin:
                    expected_status_code = 302
                    login_startswith = reverse('admin:login')
                elif can_user_access_admin and not should_data_appear:
                    # models that are directly Confidentiable or linked to Confidentiable data
                    expected_status_code = 302
                    login_startswith = reverse('admin:index')
                else:
                    expected_status_code = 200
                    login_startswith = None
                self._do_get(
                    c=response.client,
                    url=change_list_url,
                    expected_status_code=expected_status_code,
                    login_startswith=login_startswith
                )
                # only if user can access the admin site
                if can_user_access_admin:
                    text_for_data = _('{r} for {m}'.format(r=related_text, m=model_to_test._meta.model_name))
                    print(
                        _('{t} is successful ({d} {a})'.format(
                            t=confidential[self._label],
                            d=text_for_data,
                            a=_('does not appear') if not should_data_appear else _('appears')
                        ))
                    )
                else:
                    print(
                        _(
                            'Check for {m} is successful (user was redirected to login screen)'.format(
                                m=model_to_test._meta.model_name
                            )
                        )
                    )

    def _print_changelist_start_without_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin changelist test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin changelist {m}-related sub-test for {u} without a FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_create_instance_start_without_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin create instance test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin create instance {m}-related sub-test for {u} without a FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_change_instance_start_without_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin change instance test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin change instance {m}-related sub-test for {u} without a FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_change_instance_start_without_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin change instance test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin change instance {m}-related sub-test for {u} without a FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_history_start_without_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin history test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin history {m}-related sub-test for {u} without a FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_delete_start_without_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin delete test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin delete {m}-related sub-test for {u} without a FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_changelist_start_with_right_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin changelist test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin changelist {m}-related sub-test for {u} with matching FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_create_instance_start_with_right_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin create instance test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin create instance {m}-related sub-test for {u} with matching FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_change_instance_start_with_right_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin change instance test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin change instance {m}-related sub-test for {u} with matching FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_change_instance_start_with_right_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin change instance test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin change instance {m}-related sub-test '
                'for {u} with matching FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_history_start_with_right_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin history test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin history {m}-related sub-test for {u} with matching FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_delete_start_with_right_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin delete test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin delete {m}-related sub-test for {u} with matching FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_changelist_start_with_wrong_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin changelist test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin changelist {m}-related sub-test for {u} with different FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_create_instance_start_with_wrong_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin create instance test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin create instance {m}-related sub-test for {u} with different FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_change_instance_start_with_wrong_org(self, model_txt, user_role):
        """ Prints into the console the start of an admin change instance test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting admin change instance {m}-related sub-test for {u} with different FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_change_instance_start_with_wrong_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin change instance test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin change instance {m}-related sub-test '
                'for {u} with different FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_history_start_with_wrong_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin history test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin history {m}-related sub-test for {u} with different FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_load_delete_start_with_wrong_org(self, model_txt, user_role):
        """ Prints into the console the start of loading an admin delete test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _(
                '\nStarting load admin delete {m}-related sub-test for {u} with different FDP organization'.format(
                    m=model_txt,
                    u=user_role[self._label]
                )
            )
        )

    def _print_profile_search_results_start_without_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile search results test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile search results {m}-related sub-test for {u} without a '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_view_start_without_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile view test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile view content check {m}-related sub-test for {u} without a '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_load_start_without_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile load test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile load {m}-related sub-test for {u} without a '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_search_results_start_with_right_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile search results test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile search results {m}-related sub-test for {u} with matching '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_view_start_with_right_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile view test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile view content check {m}-related sub-test for {u} with matching '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_load_start_with_right_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of an officer profile load test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile load {m}-related sub-test for {u} with matching '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_search_results_start_with_wrong_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile search results test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile search results {m}-related sub-test for {u} with different '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_view_start_with_wrong_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile view test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile view content check {m}-related sub-test for {u} with '
                'different FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_profile_load_start_with_wrong_org(self, model_txt, user_role, view_txt):
        """ Prints into the console the start of a profile load test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(_('\nStarting {v} profile load {m}-related sub-test for {u} with different '
                'FDP organization'.format(m=model_txt, u=user_role[self._label], v=view_txt)))

    def _print_download_view_start_without_org(self, model_txt, user_role):
        """ Prints into the console the start of an download view test without FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(_('\nStarting download view check {m}-related '
                'sub-test for {u} without a FDP organization'.format(m=model_txt, u=user_role[self._label])))

    def _print_download_view_start_with_right_org(self, model_txt, user_role):
        """ Prints into the console the start of a download view test with matching FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(_('\nStarting download view check {m}-related '
                'sub-test for {u} with matching FDP organization'.format(m=model_txt, u=user_role[self._label])))

    def _print_download_view_start_with_wrong_org(self, model_txt, user_role):
        """ Prints into the console the start of a download view test with different FDP organization.

        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(_('\nStarting download view check {m}-related '
                'sub-test for {u} with different FDP organization'.format(m=model_txt, u=user_role[self._label])))

    def _print_changing_search_results_start_without_org(self, view_txt, model_txt, user_role):
        """ Prints into the console the start of a changing search results test without FDP organization.

        :param view_txt: Text categorizing changing search view.
        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _('\nStarting {s} changing search results {m}-related sub-test for {u} without a FDP organization'.format(
                s=view_txt, m=model_txt, u=user_role[self._label]
            ))
        )

    def _print_changing_search_results_start_with_right_org(self, view_txt, model_txt, user_role):
        """ Prints into the console the start of a changing search results test with matching FDP organization.

        :param view_txt: Text categorizing changing search view.
        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(_('\nStarting {s} changing search results {m}-related sub-test for {u} with matching '
                'FDP organization'.format(s=view_txt, m=model_txt, u=user_role[self._label])))

    def _print_changing_search_results_start_with_wrong_org(self, view_txt, model_txt, user_role):
        """ Prints into the console the start of a changing search results test with different FDP organization.

        :param view_txt: Text categorizing changing search view.
        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(_('\nStarting {s} changing search results {m}-related sub-test for {u} with different '
                'FDP organization'.format(s=view_txt, m=model_txt, u=user_role[self._label])))

    def _print_changing_update_start_without_org(self, view_txt, model_txt, user_role):
        """ Prints into the console the start of a changing update test without FDP organization.

        :param view_txt: Text categorizing changing update view.
        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(
            _('\nStarting {s} changing update view {m}-related sub-test for {u} without a FDP organization'.format(
                s=view_txt, m=model_txt, u=user_role[self._label]
            ))
        )

    def _print_changing_update_start_with_right_org(self, view_txt, model_txt, user_role):
        """ Prints into the console the start of a changing update test with matching FDP organization.

        :param view_txt: Text categorizing changing update view.
        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(_('\nStarting {s} changing update view {m}-related sub-test for {u} with matching '
                'FDP organization'.format(s=view_txt, m=model_txt, u=user_role[self._label])))

    def _print_changing_update_start_with_wrong_org(self, view_txt, model_txt, user_role):
        """ Prints into the console the start of a changing update test with different FDP organization.

        :param view_txt: Text categorizing changing update view.
        :param model_txt: Model for which tests are starting.
        :param user_role: Specific user role from self._user_roles for which test is performed.
        :return: Nothing.
        """
        print(_('\nStarting {s} changing update view {m}-related sub-test for {u} with different '
                'FDP organization'.format(s=view_txt, m=model_txt, u=user_role[self._label])))

    def _check_if_in_view(self, url, fdp_user, fdp_org):
        """ Checks whether data with different levels of confidentiality appear in a view for a FDP user.

        :param url: Url for view.
        :param fdp_user: FDP user accessing view.
        :param fdp_org: FDP organization that may be added to the data.
        :return: Nothing.
        """
        client = Client(**self._local_client_kwargs)
        client.logout()
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        response = self._do_get(c=response.client, url=url, expected_status_code=200, login_startswith=None)
        str_content = str(response.content)
        # cycle through all permutations of confidentiality for the row for data
        for confidential in self._confidentials:
            should_data_appear = self._can_user_access_data(
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key],
                has_fdp_org=confidential[self._has_fdp_org_key],
                fdp_user=fdp_user,
                fdp_org=fdp_org
            )
            if should_data_appear:
                self.assertIn(confidential[self._name_key], str_content)
            else:
                self.assertNotIn(confidential[self._name_key], str_content)
            print(
                _('{t} is successful ({d} {a})'.format(
                    t=confidential[self._label],
                    d=confidential[self._name_key],
                    a=_('does not appear') if not should_data_appear else _('appears')
                ))
            )

    def _check_if_load_view(self, fdp_user, fdp_org, id_map_dict, view_name, admin_only, load_params, exception_msg):
        """ Checks whether a view for data with different levels of confidentiality loads for a FDP user.

        :param fdp_user: FDP user loading profile view.
        :param fdp_org: FDP organization that may be added to the data.
        :param id_map_dict: A dictionary mapping unique _name_key from _confidentials into primary keys to load the
        view.
        :param view_name: Viewname parameter for reverse(...) url function.
        :param admin_only: True if only administrators can access view, false if any authenticated user can access
        view.
        :param load_params: Dictionary that can be expanded into keyword arguments that produce additional parameters
        when generating URL for view. Should not include the "pk" parameter.
        :param exception_msg: Expected exception message when attempting to load inaccessible view. Will be None if no
        exception is expected.
        :return: Nothing.
        """
        client = Client(**self._local_client_kwargs)
        client.logout()
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        # cycle through all permutations of confidentiality for the row for data
        for confidential in self._confidentials:
            should_view_load = self._can_user_access_data(
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key],
                has_fdp_org=confidential[self._has_fdp_org_key],
                fdp_user=fdp_user,
                fdp_org=fdp_org
            )
            view_pk = id_map_dict[confidential[self._name_key]]
            view_kwargs = {**{'pk': view_pk}, **load_params}
            url = reverse(view_name, kwargs=view_kwargs)
            # this view is restricted to administrators only and user is not an administrator
            if admin_only and not (fdp_user.is_administrator or fdp_user.is_superuser):
                role_text = fdp_user.role_txt
                response = self._do_get(c=response.client, url=url, expected_status_code=403, login_startswith=None)
                print(_('View for {u} is successful (displays 403 HTTP status code)'.format(u=role_text)))
            # this view is not restricted to administrators only, or user is an administrator
            else:
                # exception is expected
                if exception_msg is not None:
                    try:
                        response = self._do_get(
                            c=response.client, url=url, expected_status_code=200, login_startswith=None
                        )
                    except Exception as err:
                        self.assertEqual(str(err), exception_msg)
                    # view is expected to load
                    if should_view_load:
                        print(
                            _('{t} is successful ({d} {a})'.format(
                                t=confidential[self._label],
                                d=confidential[self._name_key],
                                a=_('view is loaded')
                            ))
                        )
                    # view is not expected to load
                    else:
                        print(
                            _('{t} is successful ({d} {a})'.format(
                                t=confidential[self._label],
                                d=confidential[self._name_key],
                                a=_('raises exception')
                            ))
                        )
                # no exception is expected
                else:
                    expected_status_code = 200 if should_view_load else 404
                    response = self._do_get(
                        c=response.client, url=url, expected_status_code=expected_status_code, login_startswith=None
                    )
                    # view is expected to load
                    if should_view_load:
                        print(
                            _('{t} is successful ({d} {a})'.format(
                                t=confidential[self._label],
                                d=confidential[self._name_key],
                                a=_('view is loaded')
                            ))
                        )
                    # view is not expected to load
                    else:
                        print(
                            _('{t} is successful ({d} {a})'.format(
                                t=confidential[self._label],
                                d=confidential[self._name_key],
                                a=_('displays {c} HTTP status code'.format(c=expected_status_code))
                            ))
                        )

    def _check_if_in_search_view(self, search_url, search_results_url, fdp_user, fdp_org, admin_only, search_params):
        """ Checks whether data with different levels of confidentiality appear in a search view for a FDP user.

        :param search_url: Url for search view.
        :param search_results_url: Url for search results view.
        :param fdp_user: FDP user accessing search.
        :param fdp_org: FDP organization that may be added to the data.
        :param admin_only: True if only administrators can access search, false if any authenticated user can access
        search.
        :param search_params: Dictionary that can be expanded into keyword arguments that produce additional parameters
        when POSTing to the search. Should not include the "search" parameter.
        :return: Nothing.
        """
        client = Client(**self._local_client_kwargs)
        client.logout()
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        # this search is restricted to administrators only and user is not an administrator
        if admin_only and not (fdp_user.is_administrator or fdp_user.is_superuser):
            role_text = fdp_user.role_txt
            # attempt to navigate to search
            response = self._do_get(c=response.client, url=search_url, expected_status_code=403, login_startswith=None)
            print(_('Search with {u} is successful (displays 403 HTTP status code)'.format(u=role_text)))
            # attempt to submit search results
            self._do_post(
                c=response.client,
                url=search_url,
                data={'search': ' '.join([c[self._name_key] for c in self._confidentials])},
                expected_status_code=403,
                login_startswith=None
            )
            print(_('Search results with {u} is successful (displays 403 HTTP status code)'.format(u=role_text)))
        # this search is not restricted to administrators only, or user is an administrator
        else:
            # navigate to search
            response = self._do_get(c=response.client, url=search_url, expected_status_code=200, login_startswith=None)
            basic_search_data = {'search': ' '.join([c[self._name_key] for c in self._confidentials])}
            search_data = {**basic_search_data, **search_params}
            # submit search
            response = self._do_post(
                c=response.client,
                url=search_url,
                data=search_data,
                expected_status_code=302,
                login_startswith=search_results_url
            )
            # navigate to search results
            response = self._do_get(
                c=response.client,
                url=response.url,
                expected_status_code=200,
                login_startswith=None
            )
            str_content = str(response.content)
            # cycle through all permutations of confidentiality for the row for data
            for confidential in self._confidentials:
                should_data_appear = self._can_user_access_data(
                    for_admin_only=confidential[self._for_admin_only_key],
                    for_host_only=confidential[self._for_host_only_key],
                    has_fdp_org=confidential[self._has_fdp_org_key],
                    fdp_user=fdp_user,
                    fdp_org=fdp_org
                )
                if should_data_appear:
                    self.assertIn(confidential[self._name_key], str_content)
                else:
                    self.assertNotIn(confidential[self._name_key], str_content)
                print(
                    _('{t} is successful ({d} {a})'.format(
                        t=confidential[self._label],
                        d=confidential[self._name_key],
                        a=_('does not appear') if not should_data_appear else _('appears')
                    ))
                )

    def _check_if_can_download(
            self, fdp_user, fdp_org, id_map_dict, view_name, model_to_download, field_with_file, base_url,
            expected_err_str
    ):
        """ Checks whether a file can be downloaded through a view for data with different levels of confidentiality.

        :param fdp_user: FDP user downloading file through view.
        :param fdp_org: FDP organization that may be added to the data.
        :param id_map_dict: A dictionary mapping unique _name_key from _confidentials into primary keys to load the
        profile.
        :param view_name: Viewname parameter for reverse(...) url function.
        :param model_to_download: Model containing instances with files that should be downloaded. Examples are:
        Attachment or PersonPhoto.
        :param field_with_file: Field in model instances that contain the path for the file to download. Examples are:
        'file' for Attachment and 'photo' for PersonPhoto.
        :param base_url: Base url for the file path.
        :param expected_err_str: Error message that is expected when a user attempts to download an inaccessible file.
        :return: Nothing.
        """
        client = Client(**self._local_client_kwargs)
        client.logout()
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        # cycle through all permutations of confidentiality for the row for data
        for confidential in self._confidentials:
            should_file_download = self._can_user_access_data(
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key],
                has_fdp_org=confidential[self._has_fdp_org_key],
                fdp_user=fdp_user,
                fdp_org=fdp_org
            )
            instance_pk = id_map_dict[confidential[self._name_key]]
            instance = model_to_download.objects.get(pk=instance_pk)
            file_path = self.__get_file_path_for_view(
                instance=instance,
                field_with_file=field_with_file,
                base_url=base_url
            )
            url = reverse(view_name, kwargs={'path': file_path})
            try:
                response = self._do_get(
                    c=response.client,
                    url=url,
                    expected_status_code=404,
                    login_startswith=None
                )
            except Exception as err:
                # attempting to download inaccessible file raises an exception
                if not should_file_download:
                    self.assertEqual(str(err), expected_err_str)
                else:
                    # we should never get here
                    raise Exception(err)
            # file is expected to download
            if should_file_download:
                print(
                    _('{t} is successful ({d} {a})'.format(
                        t=confidential[self._label],
                        d=confidential[self._name_key],
                        a=_('file can be downloaded')
                    ))
                )
            # file is not expected to download
            else:
                print(
                    _('{t} is successful ({d} {a})'.format(
                        t=confidential[self._label],
                        d=confidential[self._name_key],
                        a=_('raises exception')
                    ))
                )

    def _check_if_in_async_changing_view(self, url, fdp_user, fdp_org, admin_only):
        """ Checks whether data with different levels of confidentiality appear in an asynchronous Changing view for
        a FDP user.

        :param url: Url for asynchronous Changing view.
        :param fdp_user: FDP user accessing asynchronous Changing view.
        :param fdp_org: FDP organization that may be added to the data.
        :param admin_only: True if view is only accessible by administrators, false otherwise.
        :return: Nothing.
        """
        client = Client(**self._local_client_kwargs)
        client.logout()
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        # this asynchronous view is restricted to administrators only and user is not an administrator
        if admin_only and not (fdp_user.is_administrator or fdp_user.is_superuser):
            role_text = fdp_user.role_txt
            self._do_async_post(
                c=response.client,
                url=url,
                expected_status_code=403,
                login_startswith=None,
                data={AbstractUrlValidator.JSON_SRCH_CRT_PARAM: 'a'}
            )
            print(_('Async view for {u} is successful (displays 403 HTTP status code)'.format(u=role_text)))
        # this asynchronous view is not restricted to administrators only, or user is an administrator
        else:
            # cycle through all permutations of confidentiality for the row for data
            for confidential in self._confidentials:
                response = self._do_async_post(
                    c=response.client,
                    url=url,
                    expected_status_code=200,
                    login_startswith=None,
                    data={AbstractUrlValidator.JSON_SRCH_CRT_PARAM: confidential[self._name_key]}
                )
                str_content = str(response.content)
                should_data_appear = self._can_user_access_data(
                    for_admin_only=confidential[self._for_admin_only_key],
                    for_host_only=confidential[self._for_host_only_key],
                    has_fdp_org=confidential[self._has_fdp_org_key],
                    fdp_user=fdp_user,
                    fdp_org=fdp_org
                )
                if should_data_appear:
                    self.assertIn(confidential[self._name_key], str_content)
                else:
                    self.assertNotIn(confidential[self._name_key], str_content)
                print(
                    _('{t} is successful ({d} {a})'.format(
                        t=confidential[self._label],
                        d=confidential[self._name_key],
                        a=_('does not appear') if not should_data_appear else _('appears')
                    ))
                )

    def _assert_class_based_view(self, response, expected_view):
        """ Asserts that the response was rendered using an expected class-based view.

        :param response: Http response to check.
        :param expected_view: Class-based view that is expected to have rendered the Http response.
        :return: Nothing.
        """
        self.assertEqual(response.resolver_match.func.__name__, expected_view.as_view().__name__)

    class UserRequest:
        """ Dummy class used to simulate a request object when only the user is needed.

        """
        pass
