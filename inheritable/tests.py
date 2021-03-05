from django.test import TestCase, Client
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.util import random_hex
from django_otp.oath import totp
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse, reverse_lazy
from django.conf import settings
from fdpuser.models import FdpUser
from .models import AbstractUrlValidator
from json import dumps


class AbstractTestCase(TestCase):
    """ Abstract class from which TestCase classes can inherit.

    Provides reusable methods to log in with 2FA support.

    """
    #: Dictionary of keyword arguments that can be expanded to specify a guest administrator when creating a user.
    _guest_admin_dict = {'is_host': False, 'is_administrator': True, 'is_superuser': False}

    #: Dictionary of keyword arguments that can be expanded to specify a host administrator when createing a user.
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
        # automated tests will be skipped unless configuration is for local development
        if not settings.USE_LOCAL_SETTINGS:
            print(_('Skipping tests in {t}'.format(t=self.__class__.__name__)))
            self.skipTest(reason=_('Automated tests will only run in a local development environment'))
        # configuration is for local development
        super().setUp()

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
        key = random_hex(20).encode().decode('ascii')
        totp_device = TOTPDevice.objects.create(
            name='default', key=key, step=30, t0=0, digits=settings.TWO_FACTOR_TOTP_DIGITS,
            tolerance=1, drift=0, last_t=-1, user=user
        )
        totp_device.full_clean()
        totp_device.save()
        self.assertTrue(TOTPDevice.objects.filter(pk=totp_device.pk, key=key).exists())
        return totp_device

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
        response = c.post(
            reverse(settings.LOGIN_URL),
            {'auth-username': username, 'auth-password': password, 'login_view-current_step': 'auth'},
            follow=True
        )
        self.assertEqual(response.status_code, login_status_code)
        if login_status_code == 200:
            if two_factor_status_code is not None and two_factor is not None:
                offset = 0
                token = totp(
                    two_factor.bin_key, two_factor.step, two_factor.t0, two_factor.digits, two_factor.drift + offset
                )
                response = self._do_2fa(
                    c=response.client,
                    token=token,
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
        client = Client(REMOTE_ADDR='127.0.0.1')
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
            client = Client(REMOTE_ADDR='127.0.0.1')
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
            client = Client(REMOTE_ADDR='127.0.0.1')
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
            client = Client(REMOTE_ADDR='127.0.0.1')
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
                client = Client(REMOTE_ADDR='127.0.0.1')
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
                client = Client(REMOTE_ADDR='127.0.0.1')
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
                client = Client(REMOTE_ADDR='127.0.0.1')
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
        client = Client(REMOTE_ADDR='127.0.0.1')
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
        client = Client(REMOTE_ADDR='127.0.0.1')
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
        client = Client(REMOTE_ADDR='127.0.0.1')
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
        client = Client(REMOTE_ADDR='127.0.0.1')
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
            file_path = str(getattr(instance, field_with_file))
            if file_path.startswith(base_url):
                file_path = file_path[len(base_url):]
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
        client = Client(REMOTE_ADDR='127.0.0.1')
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

    class UserRequest:
        """ Dummy class used to simulate a request object when only the user is needed.

        """
        pass
