from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from inheritable.models import AbstractConfiguration
from inheritable.tests import AbstractTestCase, local_test_settings_required
from fdpuser.models import FdpUser, FdpOrganization
from .models import WholesaleImport
import logging

logger = logging.getLogger(__name__)


class WholesaleTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test that wholesale views are accessible by admin host users only.

    #: TODO: Ensure that templates cannot be generated for models that are not whitelisted.
    #: TODO: Ensure that templates cannot be imported for models that are not whitelisted or that do not exist.
    #: TODO: Ensure that templates cannot be imported for fields that are blacklisted or that do not exist.
    #: TODO: Ensure that file download tests match person photo download tests.
    #: TODO: Ensure that no ambiguity arises through duplicate model names in the sourcing, core, and supporting apps.
    #: TODO: Ensure PK not in template that is generated.
    #: TODO: Ensure reversion record added and is matched.
    #: TODO: Ensure bulk import records created, and no duplication.
    #: TODO: Ensure version record created for each added record including main models and models referenced by name.
    #: TODO: Ensure version record retrievable via UUID.
    #: TODO: Add with PK column, add with PK column and external ID column.
    #: TODO: Update without PK column and without external ID column.
    #: TODO: Update with PK column with some values missing.
    #: TODO: Add/update with external ID column with some values missing.
    #: TODO: Add/update with duplicate columns.
    #: TODO: Test implict model reference conversion.

    """
    def setUp(self):
        """ Ensure data required for tests has been created.

        :return: Nothing.
        """
        # skip setup and tests unless configuration is compatible
        super().setUp()
        self.assertTrue(FdpUser.objects.all().exists())
        self.assertTrue(WholesaleImport.objects.all().exists())

    @classmethod
    def setUpTestData(cls):
        """ Create an import reference during tests.

        :return: Nothing.
        """
        if not FdpUser.objects.all().exists():
            cls._create_fdp_user_without_assert(
                is_host=True,
                is_administrator=True,
                is_superuser=False,
                email_counter=1 + FdpUser.objects.all().count()
            )
        if not WholesaleImport.objects.all().exists():
            WholesaleImport.objects.create(
                action=WholesaleImport.add_value,
                file=SimpleUploadedFile(name='empty.csv', content=''),
                user=(FdpUser.objects.all().first()).email
            )

    @staticmethod
    def __can_user_access_host_admin_only(fdp_user):
        """ Checks whether a user can access a view that is restricted to host administrators only.

        :param fdp_user: User for which to check.
        :return: True if user can access views restricted to host administrator only, false otherwise.
        """
        # True for Host Administrators OR Superusers that are Active, False otherwise
        return ((fdp_user.is_administrator and fdp_user.is_host) or fdp_user.is_superuser) and fdp_user.is_active

    def __check_get_views_have_host_admin_only_access(self, fdp_user):
        """ Checks whether all URLs that are accessed through GET requests in the wholesale app are host administrator
        access only.

        :param fdp_user: FDP user for which to check URLs.
        :return: Nothing.
        """
        # all URLs accessed through GET requests in wholesale app
        get_urls = (
            reverse('wholesale:index'),
            reverse('wholesale:template'),
            reverse('wholesale:start_import'),
            reverse('wholesale:logs'),
            reverse('wholesale:log', kwargs={'pk': (WholesaleImport.objects.all().first()).pk})
        )
        can_user_access_host_admin_only = self.__can_user_access_host_admin_only(fdp_user=fdp_user)
        expected_status_code = 200 if can_user_access_host_admin_only else 403
        # cycle through URLs
        for get_url in get_urls:
            logger.debug(f'Checking GET request for {get_url} with expected status code {expected_status_code}')
            self._get_response_from_get_request(
                fdp_user=fdp_user,
                expected_status_code=expected_status_code,
                login_startswith=None,
                url=get_url
            )

    def __check_post_views_have_host_admin_only_access(self, fdp_user):
        """ Checks whether all URLs that are accessed through POST requests in the wholesale app are host administrator
        access only.

        :param fdp_user: FDP user for which to check URLs.
        :return: Nothing.
        """
        start_import_url = reverse('wholesale:start_import')
        # all URLs accessed through POST requests in wholesale app, and the corresponding example dictionaries of data
        # submitted through those POST requests
        post_tuples = (
            (
                reverse('wholesale:template'),
                {'models': (AbstractConfiguration.whitelisted_wholesale_models())[0]},
                200  # expected successful HTTP status code
            ),
            (
                start_import_url,
                {'action': WholesaleImport.add_value, 'file': SimpleUploadedFile(name='invalid.csv', content=b'a,b,c')},
                302  # expected successful HTTP status code
            )
        )
        can_user_access_host_admin_only = self.__can_user_access_host_admin_only(fdp_user=fdp_user)
        # cycle through URLs and corresponding POST data
        for post_tuple in post_tuples:
            post_url = post_tuple[0]
            post_data = post_tuple[1]
            expected_successful_status_code = post_tuple[2]
            expected_status_code = expected_successful_status_code if can_user_access_host_admin_only else 403
            logger.debug(f'Checking POST request for {post_url} with expected status code {expected_status_code}')
            # note number of imports before POSTing
            num_of_imports = WholesaleImport.objects.all().count()
            login_startswith = None if expected_status_code != 302 else reverse(
                'wholesale:log',
                # ensure log for next PK is where user was redirect
                kwargs={'pk': (WholesaleImport.objects.all().order_by('-pk').first()).pk + 1}
            )
            self._get_response_from_post_request(
                fdp_user=fdp_user,
                url=post_url,
                expected_status_code=expected_status_code,
                login_startswith=login_startswith,
                post_data=post_data
            )
            # if POST was to start an import
            if post_url == start_import_url:
                # if import was expected to start
                if expected_status_code == 302:
                    # assert that import was recorded
                    self.assertEqual(num_of_imports + 1, WholesaleImport.objects.all().count())
                # if import was not expected to start
                else:
                    # assert that import was not recorded
                    self.assertEqual(num_of_imports, WholesaleImport.objects.all().count())

    def __check_if_can_download_wholesale_import_file(self, fdp_user):
        """ Checks whether a user can download a wholesale import file.

        :param fdp_user: User attempting to download the file.
        :return: Nothing.
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
        url = reverse(
            'wholesale:download_import_file',
            kwargs={
                'path': self._get_wholesale_import_file_path_for_view(
                    wholesale_import_instance=WholesaleImport.objects.all().first()
                )
            }
        )
        can_user_access_host_admin_only = self.__can_user_access_host_admin_only(fdp_user=fdp_user)
        expected_status_code = 200 if can_user_access_host_admin_only else 403
        logger.debug(f'Checking import file download with expected status code {expected_status_code}')
        self._do_get(c=response.client, url=url, expected_status_code=expected_status_code, login_startswith=None)

    @local_test_settings_required
    def test_wholesale_host_admin_only_access(self):
        """ Test that only host administrators can access wholesale views.

        :return: Nothing
        """
        logger.debug(_('\nStarting test that only host administrators can access wholesale views'))
        num_of_users = FdpUser.objects.all().count()
        fdp_organization = FdpOrganization.objects.create(name='FdpOrganization1Wholesale')

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
            logger.debug(f'Starting {user_role[self._label]} without organization sub-test')
            self.__check_get_views_have_host_admin_only_access(fdp_user=fdp_user)
            self.__check_post_views_have_host_admin_only_access(fdp_user=fdp_user)
            self.__check_if_can_download_wholesale_import_file(fdp_user=fdp_user)
            # add organization to user
            fdp_user.fdp_organization = fdp_organization
            fdp_user.full_clean()
            fdp_user.save()
            logger.debug(f'Starting {user_role[self._label]} with organization sub-test')
            self.__check_get_views_have_host_admin_only_access(fdp_user=fdp_user)
            self.__check_post_views_have_host_admin_only_access(fdp_user=fdp_user)
            self.__check_if_can_download_wholesale_import_file(fdp_user=fdp_user)
        logger.debug(_('\nSuccessfully finished test that only host administrators can access wholesale views\n\n'))
