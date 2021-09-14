from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.apps import apps
from inheritable.models import AbstractConfiguration, AbstractSql
from inheritable.tests import AbstractTestCase, local_test_settings_required
from core.models import Person
from fdpuser.models import FdpUser, FdpOrganization
from .models import WholesaleImport, ModelHelper
import logging

logger = logging.getLogger(__name__)


class WholesaleTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test that wholesale views are accessible by admin host users only.

    (2) Test wholesale import models whitelist, specifically that:
            (A) Models omitted from whitelist are not available in the dropdown during template generation;
            (B) Models omitted from whitelist cannot be submitted for template generation; and
            (C) Models omitted from whitelist cannot be imported.

    (3) Test wholesale import model fields blacklist, specifically that:
            (A) Fields included in blacklist are not available in the dropdown during template generation;
            (B) Fields included in blacklist cannot be submitted for template generation; and
            (C) Fields included in blacklist cannot be imported.

    (4) Test that there are no ambiguous model names across apps relevant to wholesale import.

    (5) Test that internal primary key column is excluded from generated templates.

    #: TODO: Ensure reversion record added and is matched.
    #: TODO: Ensure bulk import records created, and no duplication.
    #: TODO: Ensure version record created for each added record including main models and models referenced by name.
    #: TODO: Ensure version record retrievable via UUID.
    #: TODO: Add with PK column, add with PK column and external ID column.
    #: TODO: Update without PK column and without external ID column.
    #: TODO: Update with PK column with some values missing.
    #: TODO: Add/update with external ID column with some values missing.
    #: TODO: Add/update with duplicate columns.
    #: TODO: Test implicit model reference conversion.

    """
    #: Dictionary that can be expanded into unchanging keyword arguments
    # to create a host admin user with _create_fdp_user(...) and _create_fdp_user_without_assert(...).
    __create_host_admin_user_kwargs = {'is_host': True, 'is_administrator': True, 'is_superuser': False}

    #: Name of models field to submit via POST to generate a template.
    __post_models_field = 'models'

    #: Name of action field to submit via POST to start an import.
    __post_action_field = 'action'

    #: Name of file field to submit via POST to start an import.
    __post_field_field = 'file'

    #: Characters that represent the line terminator in CSV files, i.e. to start a new CSV row.
    # See: https://docs.python.org/3/library/csv.html#csv.Dialect.lineterminator
    __csv_lineterminator = '\r\n'

    #: Name of field through which dummy person records are imported and tested.
    __field_for_person = 'name'

    #: List of all app names that are relevant when importing models through the wholesale import.
    __relevant_apps = ['core', 'sourcing', 'supporting']

    def setUp(self):
        """ Ensure data required for tests has been created.

        :return: Nothing.
        """
        # skip setup and tests unless configuration is compatible
        super().setUp()
        # create the host admin user with whom to test wholesale imports
        self.__host_admin_user = self._create_fdp_user(
            **self.__create_host_admin_user_kwargs,
            email_counter=1 + FdpUser.objects.all().count()
        )
        self.assertTrue(WholesaleImport.objects.all().exists())
        # setup URLs reused throughout this class
        self.__template_url = reverse('wholesale:template')
        self.__start_import_url = reverse('wholesale:start_import')
        # Dictionary that can be expanded into unchanging keyword arguments when expecting a successful response to a
        # GET or POST request through _get_response_from_get_request(...) and _get_response_from_post_request(...).
        self.__unchanging_success_kwargs = {
            'expected_status_code': 200,
            'login_startswith': None,
            'fdp_user': self.__host_admin_user
        }

    @classmethod
    def setUpTestData(cls):
        """ Create an import reference during tests.

        :return: Nothing.
        """
        if not FdpUser.objects.all().exists():
            cls._create_fdp_user_without_assert(
                **cls.__create_host_admin_user_kwargs,
                email_counter=1 + FdpUser.objects.all().count()
            )
        if not WholesaleImport.objects.all().exists():
            WholesaleImport.objects.create(
                action=WholesaleImport.add_value,
                file=SimpleUploadedFile(name='empty.csv', content=''),
                user=(FdpUser.objects.all().first()).email
            )

    def __get_template_post_kwargs(self, model_name):
        """ Retrieves a dictionary that can be expanded into keyword arguments to simulate submitting a POST request
        for template generation for a specific model through _get_response_from_post_request(...).

        :param model_name: Name of model for which to generate import template.
        :return: Dictionary of keyword arguments.
        """
        post_template_kwargs = self.__unchanging_success_kwargs.copy()
        post_template_kwargs['post_data'] = {self.__post_models_field: model_name}
        return post_template_kwargs

    @staticmethod
    def __get_all_user_emails():
        """ Retrieves all user emails that are currently in the database.

        :return: List of strings representing user emails.
        """
        return list(FdpUser.objects.all().values_list('email', flat=True))

    def __get_unique_user_email(self):
        """ Retrieves a unique user email that does not exist in the database.

        :return: Unique user email that does not exist in the database.
        """
        num_of_user_emails = FdpUser.objects.all().count()
        unique_user_email = f'donotreply{num_of_user_emails + 1}@google.com'
        self.assertNotIn(unique_user_email, self.__get_all_user_emails())
        return unique_user_email

    def __get_user_csv_content(self, unique_user_email):
        """ Retrieves CSV content to add a user through an "add" import.

        :param unique_user_email: Unique email for user.
        :return: String representing CSV content.
        """
        user_class_name = ModelHelper.get_str_for_cls(model_class=FdpUser)
        return f'{user_class_name}.email{self.__csv_lineterminator}{unique_user_email}'

    @classmethod
    def __get_all_person_names(cls):
        """ Retrieves all person names that are currently in the database.

        :return: List of strings representing person names.
        """
        return list(Person.objects.all().values_list(cls.__field_for_person, flat=True))

    def __get_unique_person_name(self):
        """ Retrieves a unique person name that does not exist in the database.

        :return: Unique person name that does not exist in the database.
        """
        base_unique_person_name = 'J04N D03'
        num_of_persons = Person.objects.all().count()
        unique_person_name = f'{base_unique_person_name}{num_of_persons}'
        self.assertNotIn(unique_person_name, self.__get_all_person_names())
        return unique_person_name

    def __get_person_csv_content(self, unique_person_name):
        """ Retrieves CSV content to add a person through an "add" import.

        :param unique_person_name: Unique name for person.
        :return: String representing CSV content.
        """
        person_class_name = ModelHelper.get_str_for_cls(model_class=Person)
        return f'{person_class_name}.{self.__field_for_person}{self.__csv_lineterminator}{unique_person_name}'

    def __get_start_import_post_data(self, action, str_content):
        """ Retrieves the data that can be submitted via POST to start a wholesale import.

        :param action: Action intended through import. Use WholesaleImport.add_value for adds and
        WholesaleImport.update_value for updates.
        :param str_content: String representation of the content defining the CSV template to import.
        :return: Dictionary of data to submit via POST.
        """
        num_of_imports = WholesaleImport.objects.all().count()
        content = str_content.encode(WholesaleImport.csv_encoding)
        return {
            self.__post_action_field: action,
            self.__post_field_field: SimpleUploadedFile(name=f'wholesale_test{num_of_imports}.csv', content=content)
        }

    def __get_start_import_unchanging_kwargs(self):
        """ Retrieves a dictionary that can be expanded into unchanging keyword arguments
        for _get_response_from_post_request(...) when submitting a POST request to start a wholesale import.

        :return: Dictionary that can be expanded into keyword arguments.
        """
        table = WholesaleImport.get_db_table()
        # every time NEXTVAL(...) is called, the PostgreSQL sequence will increase
        next_val = AbstractSql.exec_single_val_sql(sql_query=f"SELECT NEXTVAL('{table}_id_seq')", sql_params=[]) + 1
        return {
            'fdp_user': self.__host_admin_user,
            'expected_status_code': 302,
            'login_startswith': reverse('wholesale:log', kwargs={'pk': next_val})
        }

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
            self.__template_url,
            self.__start_import_url,
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
        # all URLs accessed through POST requests in wholesale app, and the corresponding example dictionaries of data
        # submitted through those POST requests
        post_tuples = (
            (
                self.__template_url,
                {self.__post_models_field: (AbstractConfiguration.whitelisted_wholesale_models())[0]},
                200  # expected successful HTTP status code
            ),
            (
                self.__start_import_url,
                self.__get_start_import_post_data(action=WholesaleImport.add_value, str_content='a,b,c'),
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
            login_startswith = None if expected_status_code != 302 \
                else (self.__get_start_import_unchanging_kwargs())['login_startswith']
            self._get_response_from_post_request(
                fdp_user=fdp_user,
                url=post_url,
                expected_status_code=expected_status_code,
                login_startswith=login_startswith,
                post_data=post_data
            )
            # if POST was to start an import
            if post_url == self.__start_import_url:
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

    def __check_blacklisted_field(self, unique_name, all_unique_names_callable, csv_content, class_name, field_name):
        """ Check the views that are relevant for a field that is blacklisted for wholesale import.

        :param unique_name: Unique name that will identify a dummy model instance to attempt to import through an "add".
        :param all_unique_names_callable: A callable such as __get_all_user_emails(...) or __get_all_person_names(...)
        that will retrieve a list of all unique names against which to compare the instance.
        :param csv_content: CSV content that will be used to attempt to import dummy model instance.
        :param class_name: String representation of model class to which dummy model instance belongs.
        :param field_name: String representation of field to which unique name is attempted to be assigned.
        :return: Nothing.
        """
        self.assertIn(class_name, AbstractConfiguration.whitelisted_wholesale_models())
        self.assertIn(field_name, AbstractConfiguration.blacklisted_wholesale_fields())
        str_response = self._get_response_from_get_request(url=self.__template_url, **self.__unchanging_success_kwargs)
        self.assertIn(f'"{class_name}"', str_response)
        logger.debug(f'Model {class_name} is selectable when generating a template')
        bytes_response = self._get_response_from_post_request(
            url=self.__template_url,
            cast_response_as_string=False,
            **self.__get_template_post_kwargs(model_name=class_name)
        )
        self.assertTrue(isinstance(bytes_response, bytes))
        str_response = bytes_response.decode(WholesaleImport.csv_encoding)
        self.assertTrue(str_response.startswith(f'{class_name}.id{WholesaleImport.external_id_suffix}'))
        self.assertNotIn(f'{class_name}.{field_name},', str_response)
        logger.debug(f'Model {class_name} can be submitted for template generation '
                     f'and generated template does not include field {field_name}')
        self._get_response_from_post_request(
            url=self.__start_import_url,
            post_data=self.__get_start_import_post_data(action=WholesaleImport.add_value, str_content=csv_content),
            **self.__get_start_import_unchanging_kwargs()
        )
        self.assertNotIn(unique_name, all_unique_names_callable())
        self.assertEqual(
            f'Field {field_name} is blacklisted for wholesale import.',
            (WholesaleImport.objects.all().order_by('-pk').first()).import_errors
        )
        logger.debug(f'Field {field_name} cannot be imported')

    def __check_not_whitelisted_model(self, unique_name, all_unique_names_callable, csv_content, class_name):
        """ Check the views that are relevant for a model that is not whitelisted for wholesale import.

        :param unique_name: Unique name that will identify a dummy model instance to attempt to import through an "add".
        :param all_unique_names_callable: A callable such as __get_all_user_emails(...) or __get_all_person_names(...)
        that will retrieve a list of all unique names against which to compare the instance.
        :param csv_content: CSV content that will be used to attempt to import dummy model instance.
        :param class_name: String representation of model class to which dummy model instance belongs.
        :return: Nothing.
        """
        self.assertNotIn(class_name, AbstractConfiguration.whitelisted_wholesale_models())
        str_response = self._get_response_from_get_request(url=self.__template_url, **self.__unchanging_success_kwargs)
        self.assertNotIn(f'"{class_name}"', str_response)
        logger.debug(f'Model {class_name} is not selectable when generating a template')
        str_response = self._get_response_from_post_request(
            url=self.__template_url,
            **self.__get_template_post_kwargs(model_name=class_name)
        )
        self.assertIn(f'{class_name} is not one of the available choices.', str_response)
        logger.debug(f'Model {class_name} cannot be submitted for template generation')
        self._get_response_from_post_request(
            url=self.__start_import_url,
            post_data=self.__get_start_import_post_data(action=WholesaleImport.add_value, str_content=csv_content),
            **self.__get_start_import_unchanging_kwargs()
        )
        self.assertNotIn(unique_name, all_unique_names_callable())
        self.assertEqual(
            f'Model {class_name} is not whitelisted for wholesale import.',
            (WholesaleImport.objects.all().order_by('-pk').first()).import_errors
        )
        logger.debug(f'Model {class_name} cannot be imported')

    def __check_whitelisted_model_and_not_blacklisted_field(
            self, unique_name, all_unique_names_callable, csv_content, class_name, field_name
    ):
        """ Check the views that are relevant for a model that is whitelisted and a field that is not blacklisted
        for wholesale import.

        :param unique_name: Unique name that will identify a dummy model instance to attempt to import through an "add".
        :param all_unique_names_callable: A callable such as __get_all_user_emails(...) or __get_all_person_names(...)
        that will retrieve a list of all unique names against which to compare the instance.
        :param csv_content: CSV content that will be used to attempt to import dummy model instance.
        :param class_name: String representation of model class to which dummy model instance belongs.
        :param field_name: String representation of field to which unique name is attempted to be assigned.
        :return: Nothing.
        """
        self.assertIn(class_name, AbstractConfiguration.whitelisted_wholesale_models())
        self.assertNotIn(field_name, AbstractConfiguration.blacklisted_wholesale_fields())
        str_response = self._get_response_from_get_request(
            url=self.__template_url,
            **self.__unchanging_success_kwargs
        )
        self.assertIn(f'"{class_name}"', str_response)
        logger.debug(f'Model {class_name} is selectable when generating a template')
        bytes_response = self._get_response_from_post_request(
            url=self.__template_url,
            cast_response_as_string=False,
            **self.__get_template_post_kwargs(model_name=class_name)
        )
        self.assertTrue(isinstance(bytes_response, bytes))
        str_response = bytes_response.decode(WholesaleImport.csv_encoding)
        self.assertTrue(str_response.startswith(f'{class_name}.id{WholesaleImport.external_id_suffix}'))
        self.assertIn(f'{class_name}.{field_name},', str_response)
        logger.debug(f'Model {class_name} can be submitted for template generation '
                     f'and generated template includes field {field_name}')
        self._get_response_from_post_request(
            url=self.__start_import_url,
            post_data=self.__get_start_import_post_data(action=WholesaleImport.add_value, str_content=csv_content),
            **self.__get_start_import_unchanging_kwargs()
        )
        self.assertIn(unique_name, all_unique_names_callable())
        logger.debug(f'Model {class_name} and field {field_name} can be imported')

    def __check_whitelist_for_person(self, is_whitelisted):
        """ Check the views that are relevant for whitelisted models using dummy import data with the Person model.

        :param is_whitelisted: True if the Person model is whitelisted, false if it is not whitelisted.
        :return: Nothing.
        """
        unique_person_name = self.__get_unique_person_name()
        unchanging_kwargs = {
            'unique_name': unique_person_name,
            'all_unique_names_callable': self.__get_all_person_names,
            'csv_content': self.__get_person_csv_content(unique_person_name=unique_person_name),
            'class_name': ModelHelper.get_str_for_cls(model_class=Person)
        }
        # person model is whitelisted
        if is_whitelisted:
            self.__check_whitelisted_model_and_not_blacklisted_field(
                field_name=self.__field_for_person,
                **unchanging_kwargs
            )
        # person model is not whitelisted
        else:
            self.__check_not_whitelisted_model(**unchanging_kwargs)

    def __check_blacklist_for_person_name(self, is_blacklisted):
        """ Check the views that are relevant for blacklisted fields using dummy import data with the Person model.

        :param is_blacklisted: True if the name field is blacklisted, false if it is not blacklisted.
        :return: Nothing.
        """
        unique_person_name = self.__get_unique_person_name()
        unchanging_kwargs = {
            'unique_name': unique_person_name,
            'all_unique_names_callable': self.__get_all_person_names,
            'csv_content': self.__get_person_csv_content(unique_person_name=unique_person_name),
            'class_name': ModelHelper.get_str_for_cls(model_class=Person),
            'field_name': self.__field_for_person
        }
        # name field is not blacklisted
        if not is_blacklisted:
            self.__check_whitelisted_model_and_not_blacklisted_field(**unchanging_kwargs)
        # name field is blacklisted
        else:
            self.__check_blacklisted_field(**unchanging_kwargs)

    @local_test_settings_required
    def test_wholesale_host_admin_only_access(self):
        """ Test that wholesale views are accessible by admin host users only.

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

    @local_test_settings_required
    def test_wholesale_import_model_whitelist(self):
        """ Test the wholesale import models whitelist, specifically that:
            (A) Models omitted from whitelist are not available in the dropdown during template generation;
            (B) Models omitted from whitelist cannot be submitted for template generation; and
            (C) Models omitted from whitelist cannot be imported.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import models whitelist'))
        person_class_name = ModelHelper.get_str_for_cls(model_class=Person)
        # person model is in whitelist
        logger.debug(f'Starting sub-tests for person model that is whitelisted')
        self.__check_whitelist_for_person(is_whitelisted=True)
        # person model is removed from whitelist
        logger.debug(f'Starting sub-tests for person model that is not whitelisted')
        with self.settings(
                FDP_WHOLESALE_WHITELISTED_MODELS=[
                    m for m in AbstractConfiguration.whitelisted_wholesale_models() if m != person_class_name
                ]
        ):
            self.__check_whitelist_for_person(is_whitelisted=False)
        # user model was never in whitelist, and its app is not even checked
        logger.debug(f'Starting sub-tests for user model that was never whitelisted')
        unique_user_email = self.__get_unique_user_email()
        self.__check_not_whitelisted_model(
            unique_name=unique_user_email,
            all_unique_names_callable=self.__get_all_user_emails,
            csv_content=self.__get_user_csv_content(unique_user_email=unique_user_email),
            class_name=ModelHelper.get_str_for_cls(model_class=FdpUser)
        )
        logger.debug(_('\nSuccessfully finished test for the wholesale import models whitelist\n\n'))

    @local_test_settings_required
    def test_wholesale_import_field_blacklist(self):
        """ Test wholesale import model fields blacklist, specifically that:
            (A) Fields included in blacklist are not available in the dropdown during template generation;
            (B) Fields included in blacklist cannot be submitted for template generation; and
            (C) Fields included in blacklist cannot be imported.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import fields blacklist'))
        # name field is not in blacklist
        logger.debug(f'Starting sub-tests for name field that is not blacklisted')
        self.__check_blacklist_for_person_name(is_blacklisted=False)
        # name field is added to blacklist
        logger.debug(f'Starting sub-tests for name field that is blacklisted')
        with self.settings(FDP_WHOLESALE_BLACKLISTED_FIELDS=['name']):
            self.__check_blacklist_for_person_name(is_blacklisted=True)
        logger.debug(_('\nSuccessfully finished test for the wholesale import fields blacklist\n\n'))

    @local_test_settings_required
    def test_wholesale_import_ambiguous_model_names(self):
        """ Test that there are no ambiguous model names across apps relevant to wholesale import.

        The relevant apps such as core, sourcing and supporting must only have models with names that are unique across
        all of the apps.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import ambiguous field names'))
        checked_models = []
        for app_to_check in self.__relevant_apps:
            logger.debug(f'Checking models in {app_to_check} app')
            for model_class in list(apps.get_app_config(app_to_check).get_models()):
                model_name = ModelHelper.get_str_for_cls(model_class=model_class)
                self.assertNotIn(model_name, checked_models)
                checked_models.append(model_name)
        logger.debug(_('\nSuccessfully finished test for the wholesale import ambiguous fields names\n\n'))

    @local_test_settings_required
    def test_wholesale_import_no_pk_in_template(self):
        """ Test that internal primary key column is excluded from generated templates.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import templates excluding PK columns'))
        whitelisted_wholesale_models = AbstractConfiguration.whitelisted_wholesale_models()
        for app_to_check in self.__relevant_apps:
            for model_class in list(apps.get_app_config(app_to_check).get_models()):
                model_name = ModelHelper.get_str_for_cls(model_class=model_class)
                if model_name in whitelisted_wholesale_models:
                    logger.debug(f'Checking that template generated for model {model_name} does not include '
                                 f'an internal primary key column')
                    bytes_response = self._get_response_from_post_request(
                        url=self.__template_url,
                        cast_response_as_string=False,
                        **self.__get_template_post_kwargs(model_name=model_name)
                    )
                    self.assertTrue(isinstance(bytes_response, bytes))
                    str_response = bytes_response.decode(WholesaleImport.csv_encoding)
                    self.assertTrue(str_response.startswith(f'{model_name}.id{WholesaleImport.external_id_suffix}'))
                    self.assertNotIn(f'{model_name}.id,', str_response)
                    self.assertNotIn(f'.id,', str_response)
        logger.debug(_('\nSuccessfully finished test for the wholesale templates excluding PK columns\n\n'))
