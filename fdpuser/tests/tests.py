from fdpuser.tests.common import FdpUserCommonTestCase
from django.test import Client, override_settings
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse, NoReverseMatch
from django.contrib import admin
from django.conf import settings
from django.apps import apps
from fdpuser.admin import FdpAdminSiteOTPRequired
from fdpuser.models import FdpUser, PasswordReset, FdpOrganization, FdpCSPReport
from fdpuser.forms import FdpUserCreationForm
from bulk.models import BulkImport, FdpImportFile, FdpImportMapping, FdpImportRun
from inheritable.models import AbstractConfiguration
from changing.views import IndexTemplateView as changing_index_view
from profiles.models import CommandSearch, CommandView, OfficerSearch, OfficerView
from profiles.views import IndexTemplateView as profiles_index_view
from verifying.models import VerifyContentCase, VerifyPerson, VerifyType
from fdp.configuration.abstract.constants import CONST_AZURE_AUTH_APP
from fdp.urlconf.constants import CONST_LOGIN_URL_NAME
from data_wizard.sources.models import FileSource
from axes.models import AccessLog
from two_factor.models import PhoneDevice
from two_factor.views import LoginView
from axes.models import AccessAttempt
import secrets
import logging

logger = logging.getLogger(__name__)


class FdpUserTestCase(FdpUserCommonTestCase):

    @override_settings(LEGACY_OFFICER_SEARCH_ENABLE=True)
    def test_access_to_views(self):
        """ Test access to views:
                (a) For all user types

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for access to views'))
        self.add_data_for_officer_profile()
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        for i, user_role in enumerate(self._user_roles):
            # cycle through all views to test
            for view_to_test in self._views:
                # build the view using data that was just added
                if not view_to_test[self._url_key]:
                    view_to_test[self._url_key] = reverse(
                        view_to_test[self._url_reverse_viewname_key],
                        kwargs={view_to_test[self._url_reverse_kwargs_pk_key]: self._default_pk}
                    )
                fdp_user = None
                response = None
                view_label = view_to_test[self._label]
                client = Client(**self._local_client_kwargs)
                client.logout()
                # create user and login for authenticated users
                if not user_role[self._is_anonymous_key]:
                    # create the FDP user in the test database
                    fdp_user = self._create_fdp_user(
                        is_host=user_role[self._is_host_key],
                        is_administrator=user_role[self._is_administrator_key],
                        is_superuser=user_role[self._is_superuser_key],
                        email_counter=i + num_of_users
                    )
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
                # all users can access any view where anonymous access is granted
                if view_to_test[self._is_anonymous_accessible_key]:
                    expected_status_code = 200
                # authenticated user can access any view where staff access is granted (and not change password)
                elif (not user_role[self._is_anonymous_key]) and view_to_test[self._is_staff_accessible_key] \
                        and not (view_to_test[self._url_key] in (
                            reverse('fdpuser:change_password'), reverse('fdpuser:reset_2fa'),)
                ):
                    expected_status_code = 200
                # admin user can access any view where admin is granted (and not change password)
                elif (not user_role[self._is_anonymous_key]) and user_role[self._is_administrator_key] \
                        and view_to_test[self._is_admin_accessible_key] \
                        and not (view_to_test[self._url_key] in (
                        reverse('fdpuser:change_password'), reverse('fdpuser:reset_2fa'),)
                ):
                    expected_status_code = 200
                # super user can access any view where admin is granted (and not change password)
                elif (not user_role[self._is_anonymous_key]) and (not user_role[self._is_administrator_key]) \
                        and user_role[self._is_superuser_key] \
                        and not (view_to_test[self._url_key] in (
                        reverse('fdpuser:change_password'), reverse('fdpuser:reset_2fa'),)
                ):
                    expected_status_code = 200
                # otherwise no access
                else:
                    expected_status_code = 302
                change_or_reset = (reverse('fdpuser:change_password'), reverse('fdpuser:reset_2fa'))
                login_startswith = reverse('password_reset_done') \
                    if view_to_test[self._url_key] in change_or_reset \
                    else (
                        reverse(settings.LOGIN_URL) if not str(view_to_test[self._url_key]).startswith('/admin')
                        else reverse('admin:login')
                )
                logger.debug(_('\nStarting sub-test for {v} for a {u} with expected status code {s}{r}'.format(
                    v=view_label,
                    u=user_role,
                    s=expected_status_code,
                    r=_(' with redirect to {u}'.format(u=login_startswith)) if expected_status_code == 302 else ''
                )))
                try:
                    self._do_get(
                        c=response.client if response else client,
                        url=view_to_test[self._url_key],
                        expected_status_code=expected_status_code,
                        login_startswith=login_startswith
                    )
                except AttributeError as err:
                    # anonymous user attempting to reset 2FA
                    if str(err) == '\'AnonymousUser\' object has no attribute \'email\'' \
                            and user_role[self._is_anonymous_key] \
                            and view_to_test[self._url_key] == reverse('fdpuser:reset_2fa'):
                        pass
                    else:
                        raise err
                except Exception as err:
                    # anonymous user attempting to reset password
                    if str(err) == 'Password reset rate limits have been reached' \
                            and user_role[self._is_anonymous_key] \
                            and view_to_test[self._url_key] == reverse('fdpuser:change_password'):
                        pass
                    else:
                        raise err
                # logout authenticated users and delete them
                if not user_role[self._is_anonymous_key]:
                    client.logout()
                    fdp_user.delete()
        self.delete_data_for_officer_profile()
        logger.debug(_('\nSuccessfully finished test for access to views\n\n'))

    def test_password_reset_throttling(self):
        """ Test throttling for password reset
                (a) For all user types based on IP address
                (b) For all user types based on user

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for password reset and password change throttling'))
        max_password_resets = settings.MAX_PWD_RESET_PER_IP_ADDRESS_PER_DAY
        max_password_changes = settings.MAX_PWD_RESET_PER_USER_PER_DAY
        url = reverse('password_reset')
        done_url = reverse('password_reset_done')
        chng_url = reverse('fdpuser:change_password')
        # test resetting passwords for all user types
        for j, user_role in enumerate(self._user_roles):
            client = Client(**self._local_client_kwargs)
            client.logout()
            # skip "creating" the anonymous user
            if not user_role[self._is_anonymous_key]:
                # test resetting any password
                logger.debug(_('\nStarting sub-test to reset password '
                        'for {u} by anonymous user'.format(u=user_role[self._label])))
                data = {}
                self.delete_password_resets()
                # prior to each password reset attempt, create the user
                for i in range(max_password_resets):
                    # create the FDP user in the test database
                    fdp_user = self._create_fdp_user(
                        is_host=user_role[self._is_host_key],
                        is_administrator=user_role[self._is_administrator_key],
                        is_superuser=user_role[self._is_superuser_key],
                        email='donotreply.{j}.{i}@google.com'.format(j=j, i=i)
                    )
                    data = {
                        'email': fdp_user.email,
                        'recaptcha_response_field': 'PASSED',
                        'g-recaptcha-response': 'PASSED'
                    }
                    two_factor = self._create_2fa_record(user=fdp_user)
                    # try login that is successful
                    self._do_login(
                        c=client,
                        username=fdp_user.email,
                        password=self._password,
                        two_factor=two_factor,
                        login_status_code=200,
                        two_factor_status_code=200,
                        will_login_succeed=True
                    )
                    client.logout()
                    self._do_get(c=client, url=url, expected_status_code=200, login_startswith=None)
                    self._do_post(c=client, url=url, data=data, expected_status_code=302, login_startswith=done_url)
                    logger.debug(_('Password reset #{i} is successful'.format(i=i + 1)))
                    self.assertEqual(PasswordReset.objects.all().count(), i + 1)
                    self.assertTrue(PasswordReset.objects.all().order_by('-pk')[0].ip_address)
                # assert that we've reached the limit for password resets
                self.assertEqual(PasswordReset.objects.all().count(), max_password_resets)
                # no more password resets should be allowed (will fail silently)
                self._do_get(c=client, url=url, expected_status_code=200, login_startswith=None)
                self._do_post(c=client, url=url, data=data, expected_status_code=302, login_startswith=done_url)
                # assert that no more password resets were made
                self.assertEqual(PasswordReset.objects.all().count(), max_password_resets)
                logger.debug(_('Preceding password reset was successfully blocked'))
                PasswordReset.objects.all().delete()
                self.assertEqual(PasswordReset.objects.all().count(), 0)
                # test changing own password
                # create the FDP user in the test database
                logger.debug(_('\nStarting sub-test for {u} to change their own password'.format(u=user_role[self._label])))
                fdp_user = self._create_fdp_user(
                    is_host=user_role[self._is_host_key],
                    is_administrator=user_role[self._is_administrator_key],
                    is_superuser=user_role[self._is_superuser_key],
                    email_counter=j + FdpUser.objects.all().count() + 1
                )
                # prior to each password reset attempt, create the user
                for k in range(max_password_changes):
                    two_factor = self._create_2fa_record(user=fdp_user)
                    # try login that is successful
                    self._do_login(
                        c=client,
                        username=fdp_user.email,
                        password=self._password,
                        two_factor=two_factor,
                        login_status_code=200,
                        two_factor_status_code=200,
                        will_login_succeed=True
                    )
                    self._do_get(c=client, url=chng_url, expected_status_code=302, login_startswith=url)
                    logger.debug(_('Password change #{k} is successful'.format(k=k + 1)))
                    fdp_user.set_password(self._password)
                    fdp_user.save()
                # this login should fail
                two_factor = self._create_2fa_record(user=fdp_user)
                self._do_login(
                    c=client,
                    username=fdp_user.email,
                    password=self._password,
                    two_factor=two_factor,
                    login_status_code=200,
                    two_factor_status_code=200,
                    will_login_succeed=True
                )
                try:
                    self._do_get(c=client, url=chng_url, expected_status_code=302, login_startswith=url)
                    raise Exception(_('Should never arrive here, since above password change should fail'))
                except Exception as err:
                    if not str(err) == 'Password reset rate limits have been reached':
                        raise Exception(_('Should not arrive here, but an unexpected problem occurred'))
                logger.debug(_('Following password change was successfully blocked'))
        self.delete_password_resets()
        FdpUser.objects.all().delete()
        self.assertEqual(FdpUser.objects.all().count(), 0)
        logger.debug(_('\nSuccessfully finished test for password reset and password change throttling\n\n'))

    def test_guest_admin_user_access(self):
        """ Test guest administrators accessing users for all permutations user roles.

        :return: Nothing
        """
        admin_index = reverse('admin:index')
        logger.debug(_('\nStarting test for guest administrators to access users for all permutations of user roles'))
        fdp_org_1 = FdpOrganization.objects.create(name='FdpOrganization1FdpUser')
        fdp_org_2 = FdpOrganization.objects.create(name='FdpOrganization2FdpUser')
        guest_admin_without_org = self._create_fdp_user(email='donotreply001@google.com', **self._guest_admin_dict)
        guest_admin_with_org = self._create_fdp_user(email='donotreply002@google.com', **self._guest_admin_dict)
        guest_admin_with_org.fdp_organization = fdp_org_1
        guest_admin_with_org.full_clean()
        guest_admin_with_org.save()
        without_org_ids, with_org_ids, wrong_org_ids = self.add_fdp_users(fdp_org=fdp_org_1, other_fdp_org=fdp_org_2)
        without_org_content = self.get_changelist_response(fdp_user=guest_admin_without_org)
        with_org_content = self.get_changelist_response(fdp_user=guest_admin_with_org)
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # email address will contain uniquely identifiable string
            email = (user_role[self._label]).replace(' ', '').lower()
            # for Guest Administrator without FDP organization
            logger.debug(
                'Starting changelist view sub-test for {n} for guest administrator without a FDP organization'.format(
                    n=user_role[self._label]
                )
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                self.assertIn(
                    '{email}{suffix}'.format(email=email, suffix=self.without_org_suffix),
                    without_org_content
                )
            else:
                self.check_emails_not_in_response(email=email, response_content=without_org_content)
            # for Guest Administrator with FDP organization
            logger.debug(
                'Starting changelist view sub-test for {n} for guest administrator with a FDP organization'.format(
                    n=user_role[self._label]
                )
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                self.assertIn('{email}{suffix}'.format(email=email, suffix=self.with_org_suffix), with_org_content)
            else:
                self.check_emails_not_in_response(email=email, response_content=with_org_content)
            # for Guest Administrator without FDP organization
            logger.debug(
                'Starting change instance view sub-test for {n} for '
                'guest administrator without a FDP organization'.format(n=user_role[self._label])
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                expected_status_code = 200
                login_startswith = None
            else:
                expected_status_code = 302
                login_startswith = admin_index
            self.get_change_response(
                fdp_user=guest_admin_without_org, expected_status_code=expected_status_code,
                login_startswith=login_startswith, pk=without_org_ids[email]
            )
            self.get_change_response(
                fdp_user=guest_admin_without_org, expected_status_code=302,
                login_startswith=admin_index, pk=with_org_ids[email]
            )
            self.get_change_response(
                fdp_user=guest_admin_without_org, expected_status_code=302,
                login_startswith=admin_index, pk=wrong_org_ids[email]
            )
            # for Guest Administrator with FDP organization
            logger.debug(
                'Starting change instance view sub-test for {n} for guest administrator with a FDP organization'.format(
                    n=user_role[self._label]
                )
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                expected_status_code = 200
                login_startswith = None
            else:
                expected_status_code = 302
                login_startswith = admin_index
            self.get_change_response(
                fdp_user=guest_admin_with_org, expected_status_code=expected_status_code,
                login_startswith=login_startswith, pk=with_org_ids[email]
            )
            self.get_change_response(
                fdp_user=guest_admin_with_org, expected_status_code=302,
                login_startswith=admin_index, pk=without_org_ids[email]
            )
            self.get_change_response(
                fdp_user=guest_admin_with_org, expected_status_code=302,
                login_startswith=admin_index, pk=wrong_org_ids[email]
            )
            # for Guest Administrator without FDP organization
            logger.debug(
                'Starting history view sub-test for {n} for guest administrator without a FDP organization'.format(
                    n=user_role[self._label]
                )
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                # guest administrators cannot access history
                expected_status_code = 403
                login_startswith = None
            else:
                expected_status_code = 403
                login_startswith = admin_index
            self.get_history_response(
                fdp_user=guest_admin_without_org, expected_status_code=expected_status_code,
                login_startswith=login_startswith, pk=without_org_ids[email]
            )
            self.get_history_response(
                fdp_user=guest_admin_without_org, expected_status_code=403,
                login_startswith=admin_index, pk=with_org_ids[email]
            )
            self.get_history_response(
                fdp_user=guest_admin_without_org, expected_status_code=403,
                login_startswith=admin_index, pk=wrong_org_ids[email]
            )
            # for Guest Administrator with FDP organization
            logger.debug(
                'Starting history view sub-test for {n} for guest administrator with a FDP organization'.format(
                    n=user_role[self._label]
                )
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                # guest administrators cannot access history
                expected_status_code = 403
                login_startswith = None
            else:
                expected_status_code = 403
                login_startswith = admin_index
            self.get_history_response(
                fdp_user=guest_admin_with_org, expected_status_code=expected_status_code,
                login_startswith=login_startswith, pk=with_org_ids[email]
            )
            self.get_history_response(
                fdp_user=guest_admin_with_org, expected_status_code=403,
                login_startswith=admin_index, pk=without_org_ids[email]
            )
            self.get_history_response(
                fdp_user=guest_admin_with_org, expected_status_code=403,
                login_startswith=admin_index, pk=wrong_org_ids[email]
            )
            # for Guest Administrator without FDP organization
            logger.debug(
                'Starting delete instance view sub-test for {n} '
                'for guest administrator without a FDP organization'.format(
                    n=user_role[self._label]
                )
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                expected_status_code = 200
                login_startswith = None
            else:
                expected_status_code = 302
                login_startswith = admin_index
            self.get_delete_response(
                fdp_user=guest_admin_without_org, expected_status_code=expected_status_code,
                login_startswith=login_startswith, pk=without_org_ids[email]
            )
            self.get_delete_response(
                fdp_user=guest_admin_without_org, expected_status_code=302,
                login_startswith=admin_index, pk=with_org_ids[email]
            )
            self.get_delete_response(
                fdp_user=guest_admin_without_org, expected_status_code=302,
                login_startswith=admin_index, pk=wrong_org_ids[email]
            )
            # for Guest Administrator with FDP organization
            logger.debug(
                'Starting delete instance view sub-test for {n} for guest administrator with a FDP organization'.format(
                    n=user_role[self._label]
                )
            )
            # only non-host and non-superuser
            if (not user_role[self._is_host_key]) and (not user_role[self._is_superuser_key]):
                expected_status_code = 200
                login_startswith = None
            else:
                expected_status_code = 302
                login_startswith = admin_index
            self.get_delete_response(
                fdp_user=guest_admin_with_org, expected_status_code=expected_status_code,
                login_startswith=login_startswith, pk=with_org_ids[email]
            )
            self.get_delete_response(
                fdp_user=guest_admin_with_org, expected_status_code=302,
                login_startswith=admin_index, pk=without_org_ids[email]
            )
            self.get_delete_response(
                fdp_user=guest_admin_with_org, expected_status_code=302,
                login_startswith=admin_index, pk=wrong_org_ids[email]
            )
        logger.debug(_('\nSuccessfully finished test for guest administrators to '
                'access users for all permutations of user roles\n\n'))

    def test_guest_admin_new_user(self):
        """ Test guest administrators creating new users.

        Ensure that FDP organization of new user matches FDP organization of guest administrator.

        :return: Nothing
        """
        logger.debug(_('\nStarting test for guest administrators to create new users'))
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization3FdpUser')
        num_of_users = FdpUser.objects.all().count()
        guest_admin_without_org = self._create_fdp_user(email_counter=num_of_users + 1, **self._guest_admin_dict)
        guest_admin_with_org = self._create_fdp_user(email_counter=num_of_users + 2, **self._guest_admin_dict)
        guest_admin_with_org.fdp_organization = fdp_org
        guest_admin_with_org.full_clean()
        guest_admin_with_org.save()
        # for Guest Administrator without FDP organization
        logger.debug(_('Starting sub-test for guest admin without FDP organization to create new user '
                '(check if new user\'s organization matches)'))
        email = 'donotreply0@google.com'
        without_org_create_form = FdpUserCreationForm(instance=FdpUser(email=email))
        without_org_request = self.UserRequest()
        without_org_request.user = guest_admin_without_org
        without_org_create_form.request = without_org_request
        without_org_create_form.cleaned_data = {'email': email, 'password1': self._password}
        without_org_created_user = without_org_create_form.save(commit=True)
        self.assertEqual(without_org_created_user.fdp_organization, guest_admin_without_org.fdp_organization)
        # for Guest Administrator without FDP organization
        logger.debug(_('Starting sub-test for guest admin with FDP organization to create new user '
                '(check if new user\'s organization matches)'))
        email = 'donotreply00@google.com'
        with_org_create_form = FdpUserCreationForm(instance=FdpUser(email=email))
        with_org_request = self.UserRequest()
        with_org_request.user = guest_admin_with_org
        with_org_create_form.request = with_org_request
        with_org_create_form.cleaned_data = {'email': email, 'password1': self._password}
        with_org_created_user = with_org_create_form.save(commit=True)
        self.assertEqual(with_org_created_user.fdp_organization, guest_admin_with_org.fdp_organization)
        logger.debug(_('\nSuccessfully finished test for guest administrators to create new users\n\n'))

    def test_admin_permission_escalation(self):
        """ Test administrators escalating permissions.

        :return: Nothing
        """
        logger.debug(_('\nStarting test for administrators to escalate permissions'))
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization4FdpUser')
        other_fdp_org = FdpOrganization.objects.create(name='FdpOrganization5FdpUser')
        num_of_users = FdpUser.objects.all().count()
        base_perm_escalate_dict = {'is_host': True, 'is_administrator': True, 'is_superuser': True, 'is_active': True}
        # create guest admins with and without organizations
        guest_admin_no_org = self._create_fdp_user(email_counter=num_of_users + 1, **self._guest_admin_dict)
        guest_admin_yes_org = self._create_fdp_user(email_counter=num_of_users + 2, **self._guest_admin_dict)
        guest_admin_yes_org.fdp_organization = fdp_org
        guest_admin_yes_org.full_clean()
        guest_admin_yes_org.save()
        # create users who are guest admins also that can be changed by the original guest admins
        no_org_user = self._create_fdp_user(email_counter=num_of_users + 3, **self._guest_admin_dict)
        yes_org_user = self._create_fdp_user(email_counter=num_of_users + 4, **self._guest_admin_dict)
        yes_org_user.fdp_organization = fdp_org
        yes_org_user.full_clean()
        yes_org_user.save()
        # create host admin
        host_admin = self._create_fdp_user(email_counter=num_of_users + 5, **self._host_admin_dict)
        # create users who are host admins also that can be changed by the original host admins
        host_user = self._create_fdp_user(email_counter=num_of_users + 6, **self._host_admin_dict)
        # change guest admin user without organization using another guest admin user without organization
        logger.debug(_('Starting sub-test for guest admin without FDP organization escalating another guest admin user\'s '
                'permissions and assigning them FDP organization'))
        self.check_perm_escalate(
            user_to_change=no_org_user,
            user_changing=guest_admin_no_org,
            perm_escalation_dict={**{'fdp_organization': fdp_org}, **base_perm_escalate_dict}
        )
        # change guest admin user with organization using another guest admin user with organization
        logger.debug(_('Starting sub-test for guest admin with FDP organization escalating another guest admin user\'s '
                'permissions and assigning them another FDP organization'))
        self.check_perm_escalate(
            user_to_change=yes_org_user,
            user_changing=guest_admin_yes_org,
            perm_escalation_dict={**{'fdp_organization': other_fdp_org}, **base_perm_escalate_dict}
        )
        # change host admin user without organization using another host admin user without organization
        logger.debug(_('Starting sub-test for host admin without FDP organization escalating another host admin user\'s '
                'permissions'))
        self.check_perm_escalate(
            user_to_change=host_user,
            user_changing=host_admin,
            perm_escalation_dict={**{'fdp_organization': None}, **base_perm_escalate_dict}
        )
        logger.debug(_('\nSuccessfully finished test for administrators to escalate permissions\n\n'))

    def test_guest_admin_host_only_access(self):
        """ Test guest administrators accessing host-only views.

        :return: Nothing
        """
        logger.debug(_('\nStarting test for guest administrators to access host-only views'))
        num_of_users = FdpUser.objects.all().count()
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization6FdpUser')
        guest_admin = self._create_fdp_user(email_counter=num_of_users + 1, **self._guest_admin_dict)
        guest_admin.fdp_organization = fdp_org
        guest_admin.full_clean()
        guest_admin.save()
        # cycle through all models to test
        for model_to_test in [
            PasswordReset, FdpOrganization, FdpCSPReport,
            BulkImport, FdpImportFile, FdpImportMapping, FdpImportRun,
            FileSource,
            AccessLog, AccessAttempt,
            PhoneDevice,
            CommandSearch, CommandView, OfficerSearch, OfficerView,
            VerifyContentCase, VerifyPerson, VerifyType
        ] + (
            [] if CONST_AZURE_AUTH_APP not in settings.INSTALLED_APPS else [
                #: Django Social Auth package may not be installed
                #: See https://python-social-auth.readthedocs.io/en/latest/configuration/django.html
                apps.get_model(CONST_AZURE_AUTH_APP, 'Association'),
                apps.get_model(CONST_AZURE_AUTH_APP, 'None'),
                apps.get_model(CONST_AZURE_AUTH_APP, 'UserSocialAuth'),
            ]
        ):
            url = reverse(
                'admin:{app}_{model_to_test}_changelist'.format(
                    app=model_to_test._meta.app_label,
                    model_to_test=model_to_test._meta.model_name
                )
            )
            logger.debug(
                'Starting host-only view access sub-test for {n} for guest administrator'.format(
                    n=model_to_test._meta.model_name
                )
            )
            self._get_response_from_get_request(
                fdp_user=guest_admin,
                url=url,
                expected_status_code=403,
                login_startswith=None
            )
        logger.debug(_('\nSuccessfully finished test for guest administrators to access host-only views\n\n'))

    def test_local_dev_configuration(self):
        """ Test login view, 2FA, URL patterns and file serving for a configuration that is intended for a local
        development environment.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for login view, 2FA, URL patterns and '
                'file serving for local development configuration'))
        # test is only relevant for local development configuration
        self.assertTrue(AbstractConfiguration.is_using_local_configuration())
        self.assertFalse(AbstractConfiguration.is_using_azure_configuration())
        logger.debug('Checking that view for login is from Django Two-Factor Authentication package')
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
        self._assert_class_based_view(response=response, expected_view=LoginView)
        logger.debug('Checking that 2FA is encountered after Django authentication with username and password')
        host_admin = self._create_fdp_user(email_counter=FdpUser.objects.all().count() + 1, **self._host_admin_dict)
        user_kwargs = {'username': host_admin.email, 'password': self._password, 'login_status_code': 200}
        self._create_2fa_record(user=host_admin)
        response = self._do_django_username_password_authentication(c=response.client, **user_kwargs)
        # default 2FA Login view is expected for OTP step
        self._assert_2fa_step_in_login_view(response=response, expected_view=LoginView)
        logger.debug('Checking that social-auth login is not defined')
        self.assertRaises(
            NoReverseMatch,
            reverse,
            'social:begin',
            kwargs={'args': [AbstractConfiguration.azure_active_directory_provider]}
        )
        for static_file_type in self.get_static_file_types(callable_name='serve_static_file'):
            logger.debug('Checking that {t} files are served '
                  'using serve_static_file(...) method'.format(t=static_file_type['type']))
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
        self._assert_username_and_password_step_in_login_view(response=response, expected_view=LoginView)
        logger.debug('Checking that 2FA is enforced for the Admin site')
        self.assertEqual(admin.site.__class__, FdpAdminSiteOTPRequired)
        logger.debug(_('\nSuccessfully finished test for '
                'login view, 2FA, URL patterns and file serving for local development configuration\n\n'))

    def test_axes_redacts_attempted_passwords(self):
        """Test to check that plain-text password attempts aren't stored by Axes in access attempts records.
        """
        logger.debug(_('\nStarting test for Axes redacts attempted passwords in logs'))

        def axes_record_contains(value: str, record: AccessAttempt) -> bool:
            """Return True if given string found in an AxesAttempt record. Iterates through all attributes of a given
            object.

            :param value: String to search for
            :type value: str
            :param record: AxesAttempt record
            :type record: object
            :return: True if the string is found, False if not
            :rtype: bool
            """
            for element in record.__dict__.keys():
                try:
                    if value in record.__dict__[element]:
                        return True
                except TypeError:
                    pass
            return False

        username = secrets.token_urlsafe().replace('-', '').replace('_', '') + "@example.com"
        password = secrets.token_urlsafe().replace('-', '').replace('_', '')
        client = Client(**self._local_client_kwargs)
        response = self._do_django_username_password_authentication(
            c=client,
            username=username,
            password=password,
            login_status_code=200
        )

        axes_attempt_record = AccessAttempt.objects.all()[0]

        if not axes_record_contains(username, axes_attempt_record):
            raise Exception("Username not found in Axes attempt record. Can't complete test.")

        self.assertTrue(not axes_record_contains(password, axes_attempt_record),
                        "Plain-text login attempt password found in Axes record.")
        logger.debug(_('\nSuccessfully finished test for Axes redacts attempted passwords in logs\n\n'))

    def test_eula_requirement(self):
        """ Test enforcement of EULA requirement, including:
                (a) EULA is not required when EULAs are disabled;
                (b) EULA agreement is first required before accessing profiles and changing index pages; and
                (c) EULA agreement is only required once when accessing profiles and changing index pages.
        :return: Nothing.
        """
        logger.debug(_('\nStarting test for enforcement of EULA requirements'))
        num_of_users = FdpUser.objects.all().count()
        fdp_organization = FdpOrganization.objects.create(name='FdpOrganization7FdpUser')
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # user without organization
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # log user in
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
            all_kwargs = {'fdp_user': fdp_user, 'response': response}
            staff_kwargs = {'url': reverse('profiles:index'), 'expected_view': profiles_index_view, **all_kwargs}
            admin_kwargs = {'url': reverse('changing:index'), 'expected_view': changing_index_view, **all_kwargs}
            logger.debug(f'Starting {user_role[self._label]} without organization sub-test')
            self.check_for_eula(**staff_kwargs)
            # if user is an administrator or superuser, then try the admin URL also
            if fdp_user.is_administrator or fdp_user.is_superuser:
                self.check_for_eula(**admin_kwargs)
            logger.debug(f'Starting {user_role[self._label]} with organization sub-test')
            # add organization to user
            fdp_user.fdp_organization = fdp_organization
            fdp_user.full_clean()
            fdp_user.save()
            self.check_for_eula(**staff_kwargs)
            # if user is an administrator or superuser, then try the admin URL also
            if fdp_user.is_administrator or fdp_user.is_superuser:
                self.check_for_eula(**admin_kwargs)
        logger.debug(_('\nSuccessfully finished test for enforcement of EULA requirements\n\n'))

    @override_settings(
        ROOT_URLCONF='fdp.urlconf.test.federated_login_local_urls',
        FEDERATED_LOGIN_OPTIONS=[{'label': '...', 'url_pattern_name': 'two_factor:login', 'url_pattern_args': []}]
    )
    def test_federated_login_for_local(self):
        """ Test federated login is integrated during local settings, including:
            (a) Federated login page appears first for all permutations of user roles when user is not authenticated;
            and
            (b) Federated login page does not appear for all permutations of user roles when user is authenticated.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for federated login for local settings'))
        self.exercise_federated_login_for_all()
        logger.debug(_('\nSuccessfully finished test for federated login for local settings\n\n'))
