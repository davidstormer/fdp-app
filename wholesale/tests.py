from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from inheritable.models import AbstractConfiguration, AbstractSql
from inheritable.tests import AbstractTestCase, local_test_settings_required
from bulk.models import BulkImport
from core.models import Person, PersonAlias, PersonIdentifier
from fdpuser.models import FdpUser, FdpOrganization
from supporting.models import Trait, PersonIdentifierType
from .models import WholesaleImport, WholesaleImportRecord, ModelHelper
from reversion.models import Revision, Version
from csv import writer as csv_writer
from json import dumps as json_dumps
from itertools import product
from io import StringIO
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

    (6) Test that data integrity is preserved during "add" imports, including for combinations when:
                (A) Models may or may not have external IDs defined;
                (B) Models may reference foreign keys via PK, name or external ID;
                (C) Models may reference many-to-many fields via PK, name or external ID; and
                (D) Models may reference other models on the same row through explicit references, on the same row
                    through implicit references, or on a different row through explicit references.

    #: TODO: Ensure bulk import records created, and no duplication.
    #: TODO: Ensure version record created for each added record including main models and models referenced by name.
    #: TODO: Add with PK column, add with PK column and external ID column.
    #: TODO: Update without PK column and without external ID column.
    #: TODO: Update with PK column with some values missing.
    #: TODO: Add/update with external ID column with some values missing.
    #: TODO: Add/update with duplicate columns.

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

    #: Name of the attribute that stores the "test" external ID that is associated with an instance.
    __test_external_id_attr = '_test_ext_id'

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
        # need at least 3 traits
        while Trait.objects.all().count() < 3:
            Trait.objects.create(name=f'wholesale_test{Trait.objects.all().count()}')
        # need at least 3 person identifier types
        while PersonIdentifierType.objects.all().count() < 3:
            PersonIdentifierType.objects.create(name=f'wholesale_test{PersonIdentifierType.objects.all().count()}')

    class FieldToImport(object):
        """ Represents a field to import through a CSV template.

        """
        def __init__(self, callable_for_values, column_heading, *args, **kwargs):
            """ Initializes a field to import through a CSV template.

            :param callable_for_values: A callable that will be passed the row number as a single argument to generate
            the value for that row. Call wil be in the form of: callable_for_values(row_num=...).
            :param column_heading: The name of the column in the CSV template.
            :param args:
            :param kwargs:
            """
            super().__init__(*args, **kwargs)
            self.callable_for_values = callable_for_values
            self.column_heading = column_heading

    def __add_external_ids(self, instances, class_name):
        """ Adds external IDs to an iterable of instances. External IDs will be created in the test database and also
        linked to each instance through an attribute whose name is defined in __test_external_id_attr.

        :param instances: Iterable of instances to which to add external IDs.
        :param class_name: String representation of class to which instances all belong.
        :return: Nothing.
        """
        for instance in instances:
            bulk_import = BulkImport.objects.create(
                source_imported_from='wholesale import test',
                table_imported_from=class_name,
                pk_imported_from=f'{class_name}{BulkImport.objects.all().count()}',
                table_imported_to=class_name,
                pk_imported_to=instance.pk,
                data_imported=json_dumps({}, default=str)
            )
            setattr(instance, self.__test_external_id_attr, bulk_import.pk_imported_from)

    def __get_traits_callables(self):
        """ Retrieves the by primary key, by name, and by external ID callables for the Traits model that can be used
        in instances of FieldToImport.

        These callables are used to retrieve the correct trait(s) depending on the row number in the CSV import.

        :return: A tuple:
                    [0] Traits by primary key callable;
                    [1] Traits by name callable; and
                    [2] Traits by external ID callable.
        """
        trait_class_name = ModelHelper.get_str_for_cls(model_class=Trait)
        three_traits = Trait.objects.all()[:3]
        self.__add_external_ids(instances=three_traits, class_name=trait_class_name)
        traits_callable = lambda row_num, attr_name: '' if row_num % 3 == 0 else (
            getattr(three_traits[0], attr_name) if row_num % 3 == 1
            else f'{getattr(three_traits[1], attr_name)}, {getattr(three_traits[2], attr_name)}'
        )
        traits_by_pk_callable = lambda row_num: traits_callable(row_num=row_num, attr_name='pk')
        traits_by_name_callable = lambda row_num: traits_callable(row_num=row_num, attr_name='name')
        traits_by_ext_callable = lambda row_num: traits_callable(
            row_num=row_num,
            attr_name=self.__test_external_id_attr
        )
        return traits_by_pk_callable, traits_by_name_callable, traits_by_ext_callable

    def __get_person_identifier_types_callables(self):
        """ Retrieves the by primary key, by name, and by external ID callables for the PersonIdentifierType model
        that can be used in instances of FieldToImport.

        These callables are used to retrieve the correct person identifier type(s) depending on the row number in the
        CSV import.

        :return: A tuple:
                    [0] Person identifier types by primary key callable;
                    [1] Person identifier types by name callable; and
                    [2] Person identifier types by external ID callable.
        """
        identifier_type_class_name = ModelHelper.get_str_for_cls(model_class=PersonIdentifierType)
        three_identifier_types = PersonIdentifierType.objects.all()[:3]
        self.__add_external_ids(instances=three_identifier_types, class_name=identifier_type_class_name)
        identifier_type_callable = lambda row_num, attr_name: getattr(three_identifier_types[(row_num % 3)], attr_name)
        identifier_type_by_pk_callable = lambda row_num: identifier_type_callable(
            row_num=row_num,
            attr_name='pk'
        )
        identifier_type_by_name_callable = lambda row_num: identifier_type_callable(
            row_num=row_num,
            attr_name='name'
        )
        identifier_type_by_ext_callable = lambda row_num: identifier_type_callable(
            row_num=row_num,
            attr_name=self.__test_external_id_attr
        )
        return identifier_type_by_pk_callable, identifier_type_by_name_callable, identifier_type_by_ext_callable

    @staticmethod
    def __get_csv_rows_for_import(num_of_rows, fields_to_import):
        """ Retrieves the rows that represent the CSV to import.

        :param num_of_rows: Number of rows to generate for CSV import.
        :param fields_to_import: List of FieldToImport instances used to generated CSV import.
        :return: List of lists representing CSV to import.
        """
        csv_headings_row = [[f.column_heading for f in fields_to_import]]
        csv_data_rows = [[f.callable_for_values(row_num=i) for f in fields_to_import] for i in range(0, num_of_rows)]
        return csv_headings_row + csv_data_rows

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

    @staticmethod
    def __print_integrity_subtest_message(cur_combo):
        """ Print/log a message describing the current import "add" integrity subtest.

        :param cur_combo: Dictionary with relevant variables to generate message.
        :return: Nothing.
        """
        has = 'has'
        hasnt = 'doesn\'t have'
        implicit = 'implicit'
        explicit_same_row = 'explicit on the same row'
        explicit_different_row = 'explicit on a different row'
        txt_ext = 'external ID'
        txt_pk = 'PK'
        txt_name = 'name'
        txt_alias = implicit if not cur_combo['is_person_alias_to_person_explicit'] else (
            explicit_same_row if cur_combo['person_alias_to_person_callable'] == cur_combo['person_ext_id_callable']
            else explicit_different_row
        )
        txt_identifier = implicit if not cur_combo['is_person_identifier_to_person_explicit'] else (
            explicit_same_row
            if cur_combo['person_identifier_to_person_callable'] == cur_combo['person_ext_id_callable']
            else explicit_different_row
        )
        txt_trait = txt_ext if cur_combo['trait_callable'] == cur_combo['traits_by_ext_callable'] else (
            txt_pk if cur_combo['trait_callable'] == cur_combo['traits_by_pk_callable'] else txt_name
        )
        txt_type = txt_ext if cur_combo['identifier_type_callable'] == cur_combo['identifier_types_by_ext_callable'] \
            else (
                txt_pk if cur_combo['identifier_type_callable'] == cur_combo['identifier_types_by_pk_callable']
                else txt_name
            )
        logger.debug(
            f'Starting sub-test where person {has if cur_combo["person_has_ext_id"] else hasnt} external ID, '
            f'person alias {has if cur_combo["person_alias_has_ext_id"] else hasnt} external ID, '
            f'person identifier {has if cur_combo["person_identifier_has_ext_id"] else hasnt} external ID, '
            f'person alias to person reference is {txt_alias}, '
            f'person identifier to person reference is {txt_identifier}, '
            f'traits are referenced by {txt_trait}, '
            f'identifier types are referenced by {txt_type}.'
        )

    def __do_integrity_subtest_import(self, num_of_rows, cur_combo):
        """ Perform a wholesale "add" import intended for a subtest within the integrity test.

        :param num_of_rows: Number of rows in the CSV template that will be imported.
        :param cur_combo: Dictionary containing variables used to define the import.
        :return: Nothing.
        """
        f = self.FieldToImport
        person_fields = [
            f(callable_for_values=cur_combo['person_ext_id_callable'], column_heading=cur_combo['person_ext_id_col'])
        ] if cur_combo['person_has_ext_id'] else []
        person_fields += [
            f(callable_for_values=cur_combo['person_name_callable'], column_heading=cur_combo['person_name_col']),
            f(callable_for_values=cur_combo['trait_callable'], column_heading=cur_combo['trait_col'])
        ]
        person_alias_fields = [
            f(
                callable_for_values=cur_combo['person_alias_ext_id_callable'],
                column_heading=cur_combo['person_alias_ext_id_col']
            )
        ] if cur_combo['person_alias_has_ext_id'] else []
        person_alias_fields += [
            f(
                callable_for_values=cur_combo['person_alias_name_callable'],
                column_heading=cur_combo['person_alias_name_col']
            ),
        ]
        if cur_combo['is_person_alias_to_person_explicit']:
            person_alias_fields += [
                f(
                    callable_for_values=cur_combo['person_alias_to_person_callable'],
                    column_heading=cur_combo['person_alias_to_person_col']
                )
            ]
        person_identifier_fields = [
            f(
                callable_for_values=cur_combo['person_identifier_ext_id_callable'],
                column_heading=cur_combo['person_identifier_ext_id_col'])
        ] if cur_combo['person_identifier_has_ext_id'] else []
        person_identifier_fields += [
            f(
                callable_for_values=cur_combo['person_identifier_identifier_callable'],
                column_heading=cur_combo['person_identifier_identifier_col']
            ),
            f(
                callable_for_values=cur_combo['identifier_type_callable'],
                column_heading=cur_combo['identifier_type_col']
            ),
        ]
        if cur_combo['is_person_identifier_to_person_explicit']:
            person_identifier_fields += [
                f(
                    callable_for_values=cur_combo['person_identifier_to_person_callable'],
                    column_heading=cur_combo['person_identifier_to_person_col']
                )
            ]
        fields_to_import = person_fields + person_alias_fields + person_identifier_fields
        csv_rows = self.__get_csv_rows_for_import(num_of_rows=num_of_rows, fields_to_import=fields_to_import)
        with StringIO() as string_io:
            writer = csv_writer(
                string_io,
                delimiter=WholesaleImport.csv_delimiter,
                quotechar=WholesaleImport.csv_quotechar
            )
            for csv_row in csv_rows:
                writer.writerow(csv_row)
            csv_content = string_io.getvalue()
            self._get_response_from_post_request(
                url=self.__start_import_url,
                post_data=self.__get_start_import_post_data(
                    action=WholesaleImport.add_value,
                    str_content=csv_content
                ),
                **self.__get_start_import_unchanging_kwargs()
            )

    def __verify_one_version(self, response, app_label, instance):
        """ Verifies that a single version has been created and can be successfully loaded for a model instance.

        Version is created through the django-reversion package.

        :param response: Http response returned after successful login of user. Contains "client" attribute.
        :param app_label: Lowercase name for Django app in which model for instance is defined.
        :param instance: Model instance for which to verify version.
        :return: Nothing.
        """
        model_name = (ModelHelper.get_str_for_cls(model_class=type(instance))).lower()
        all_versions = Version.objects.get_for_object(instance)
        self.assertEqual(1, len(all_versions))
        response = self._do_get(
            c=response.client,
            url=f'/admin/{app_label}/{model_name}/{instance.pk}/history/{(all_versions[0]).pk}/',
            expected_status_code=200,
            login_startswith=None
        )
        response_str = str(response.content)
        self.assertNotIn('incompatible', response_str)
        self.assertNotIn('cannot', response_str)
        self.assertIn('Press the save button below to revert to this version of the object.', response_str)

    def __verify_bulk_records(self, model_name, has_external, num_of_rows):
        """ Verifies that a number of bulk import records were created for a particular model.

        :param model_name: Name of model for which to check bulk import records.
        :param has_external: True if model is expected to have bulk import records, false otherwise.
        :param num_of_rows: Number of bulk import records that the model is expected to have. Ignored if has_external
        is False.
        :return: Nothing.
        """
        self.assertEqual(
            BulkImport.objects.filter(table_imported_to=model_name).count(),
            0 if not has_external else num_of_rows
        )

    def __verify_integrity_person_by_person(
            self, response, cur_combo, has_external_person_col, is_external_person_col_auto,
            has_external_person_alias_col, has_external_person_identifier_col, uuid
    ):
        """ Verify the integrity of the data imported through an "add" import person-by-person.

        :param response: Http response returned after successful login of user. Contains "client" attribute.
        :param cur_combo: Dictionary containing variables used to define the import.
        :param has_external_person_col: True if external IDs exist for persons, false otherwise.
        :param is_external_person_col_auto: True if the external IDs for persons were generated automatically, false if
        they were included in the CSV.
        :param has_external_person_alias_col: True if external IDs exist for person aliases, false otherwise.
        :param has_external_person_identifier_col: True if external IDs exist for person identifiers, false otherwise.
        :param uuid: UUID for relevant wholesale import.
        :return: Nothing.
        """
        person_class = cur_combo['person_class_name']
        person_alias_class = cur_combo['person_alias_class_name']
        person_identifier_class = cur_combo['person_identifier_class_name']
        w = WholesaleImportRecord.objects.all()
        f = ['instance_pk', 'row_num']
        all_person_wholesale_records = list(w.filter(model_name=person_class).values(*f))
        all_person_alias_wholesale_records = list(w.filter(model_name=person_alias_class).values(*f))
        all_person_identifier_wholesale_records = list(w.filter(model_name=person_identifier_class).values(*f))
        b = BulkImport.objects.all()
        f = ['pk_imported_to', 'pk_imported_from']
        all_person_bulk_records = list(b.filter(table_imported_to='Person').values(*f))
        all_person_alias_bulk_records = list(b.filter(table_imported_to='PersonAlias').values(*f))
        all_person_identifier_bulk_records = list(b.filter(table_imported_to='PersonIdentifier').values(*f))
        all_trait_bulk_records = list(b.filter(table_imported_to='Trait').values(*f))
        all_identifier_type_bulk_records = list(b.filter(table_imported_to='PersonIdentifierType').values(*f))
        for person in Person.objects.all().prefetch_related(
                'person_aliases', 'person_identifiers__person_identifier_type', 'traits'
        ):
            person_aliases = person.person_aliases.all()
            person_identifiers = person.person_identifiers.all()
            self.assertEqual(1, person_aliases.count())
            self.assertEqual(1, person_identifiers.count())
            person_alias = person_aliases.first()
            person_identifier = person_identifiers.first()
            person_wholesale_records = [r for r in all_person_wholesale_records if r['instance_pk'] == person.pk]
            person_alias_wholesale_records = \
                [r for r in all_person_alias_wholesale_records if r['instance_pk'] == person_alias.pk]
            person_identifier_wholesale_records = \
                [r for r in all_person_identifier_wholesale_records if r['instance_pk'] == person_identifier.pk]
            self.assertEqual(1, len(person_wholesale_records))
            self.assertEqual(1, len(person_alias_wholesale_records))
            self.assertEqual(1, len(person_identifier_wholesale_records))
            p_kwargs = {'row_num': person_wholesale_records[0]['row_num'] - 1}
            pa_kwargs = {'row_num': person_alias_wholesale_records[0]['row_num'] - 1}
            pi_kwargs = {'row_num': person_identifier_wholesale_records[0]['row_num'] - 1}
            self.__verify_one_version(response=response, app_label='core', instance=person)
            self.__verify_one_version(response=response, app_label='core', instance=person_alias)
            self.__verify_one_version(response=response, app_label='core', instance=person_identifier)
            person_bulk_records = [r for r in all_person_bulk_records if r['pk_imported_to'] == person.pk]
            self.assertEqual(len(person_bulk_records), 0 if not has_external_person_col else 1)
            person_alias_bulk_records = \
                [r for r in all_person_alias_bulk_records if r['pk_imported_to'] == person_alias.pk]
            self.assertEqual(len(person_alias_bulk_records), 0 if not has_external_person_alias_col else 1)
            person_identifier_bulk_records = \
                [r for r in all_person_identifier_bulk_records if r['pk_imported_to'] == person_identifier.pk]
            self.assertEqual(len(person_identifier_bulk_records), 0 if not has_external_person_identifier_col else 1)
            if has_external_person_col:
                # external IDs for persons were automatically generated
                if is_external_person_col_auto:
                    self.assertEqual(
                        person_bulk_records[0]['pk_imported_from'],
                        WholesaleImport.get_auto_external_id(uuid=uuid, group=1, row_num=p_kwargs['row_num'] + 1)
                    )
                else:
                    self.assertEqual(person_bulk_records[0]['pk_imported_from'],
                                     cur_combo['person_ext_id_callable'](**p_kwargs))
            if has_external_person_alias_col:
                self.assertEqual(person_alias_bulk_records[0]['pk_imported_from'],
                                 cur_combo['person_alias_ext_id_callable'](**pa_kwargs))
            if has_external_person_identifier_col:
                self.assertEqual(person_identifier_bulk_records[0]['pk_imported_from'],
                                 cur_combo['person_identifier_ext_id_callable'](**pi_kwargs))
            self.assertEqual(cur_combo['person_name_callable'](**p_kwargs), person.name)
            trait_callable = cur_combo['trait_callable']
            traits_set = set([str(t.pk) for t in person.traits.all()])
            if trait_callable == cur_combo['traits_by_pk_callable']:
                traits_by_pk = str(trait_callable(**p_kwargs))
                trait_pks = traits_by_pk.split(',')
                self.assertEqual(traits_set, set([t.strip() for t in trait_pks if t.strip() != '']))
            elif trait_callable == cur_combo['traits_by_ext_callable']:
                traits_by_ext = trait_callable(**p_kwargs)
                trait_exts = traits_by_ext.split(',')
                self.assertEqual(
                    set([b['pk_imported_from'] for b in all_trait_bulk_records
                         if str(b['pk_imported_to']) in traits_set]),
                    set([t.strip() for t in trait_exts if t.strip() != '']))
            else:
                traits_by_name = trait_callable(**p_kwargs)
                trait_names = traits_by_name.split(',')
                self.assertEqual(set([t.name for t in person.traits.all()]),
                                 set([t.strip() for t in trait_names if t.strip() != '']))
            self.assertEqual(cur_combo['person_alias_name_callable'](**pa_kwargs), person_alias.name)
            self.assertEqual(cur_combo['person_identifier_identifier_callable'](**pi_kwargs),
                             person_identifier.identifier)
            identifier_type_callable = cur_combo['identifier_type_callable']
            person_identifier_type = person_identifier.person_identifier_type
            csv_val = identifier_type_callable(**pi_kwargs)
            if identifier_type_callable == cur_combo['identifier_types_by_pk_callable']:
                self.assertEqual(person_identifier_type.pk, csv_val)
            elif identifier_type_callable == cur_combo['identifier_types_by_ext_callable']:
                identifier_type_bulk_records = \
                    [b for b in all_identifier_type_bulk_records if b['pk_imported_to'] == person_identifier_type.pk]
                self.assertEqual(len(identifier_type_bulk_records), 1)
                self.assertEqual(identifier_type_bulk_records[0]['pk_imported_from'], csv_val)
            else:
                self.assertEqual(person_identifier.person_identifier_type.name, csv_val)

    def __verify_integrity_subtest_import(self, num_of_rows, cur_combo):
        """ Verifies data that was imported through a wholesale "add" import for a subtest within the integrity test.

        :param num_of_rows: Number of rows in the CSV template that will be imported.
        :param cur_combo: Dictionary containing variables used to define the import.
        :return: Nothing.
        """
        wholesale_import = WholesaleImport.objects.all().order_by('-pk').first()
        num_of_expected_records = len(wholesale_import.import_models) * num_of_rows
        wholesale_import_records = WholesaleImportRecord.objects.filter(wholesale_import_id=wholesale_import.pk)
        person_class = cur_combo['person_class_name']
        person_alias_class = cur_combo['person_alias_class_name']
        person_identifier_class = cur_combo['person_identifier_class_name']
        self.assertEqual(wholesale_import.action, WholesaleImport.add_value)
        self.assertEqual(wholesale_import.import_errors, '')
        self.assertEqual(
            set(list(wholesale_import.import_models)), {person_class, person_alias_class, person_identifier_class}
        )
        fdp_user = (self.__get_start_import_unchanging_kwargs())['fdp_user']
        self.assertEqual(wholesale_import.user, fdp_user.email)
        self.assertEqual(wholesale_import_records.count(), num_of_expected_records)
        self.assertEqual(wholesale_import_records.filter(errors='').count(), num_of_expected_records)
        self.assertEqual(wholesale_import_records.filter(model_name=person_class).count(), num_of_rows)
        self.assertEqual(wholesale_import_records.filter(model_name=person_alias_class).count(), num_of_rows)
        self.assertEqual(wholesale_import_records.filter(model_name=person_identifier_class).count(), num_of_rows)
        self.assertEqual(wholesale_import.error_rows, 0)
        self.assertEqual(wholesale_import.imported_rows, num_of_expected_records)
        self.assertEqual(Person.objects.all().count(), num_of_rows)
        self.assertEqual(PersonAlias.objects.all().count(), num_of_rows)
        self.assertEqual(PersonIdentifier.objects.all().count(), num_of_rows)
        self.assertEqual(getattr(Revision, 'objects').all().count(), 1)
        revision = getattr(Revision, 'objects').all().first()
        self.assertEqual(revision.user.pk, fdp_user.pk)
        uuid = wholesale_import.uuid
        self.assertIn(uuid, revision.comment)
        person_content_type = ContentType.objects.get(app_label='core', model='person')
        self.assertEqual(Version.objects.filter(content_type=person_content_type).count(), num_of_rows)
        person_alias_content_type = ContentType.objects.get(app_label='core', model='personalias')
        self.assertEqual(Version.objects.filter(content_type=person_alias_content_type).count(), num_of_rows)
        person_identifier_content_type = ContentType.objects.get(app_label='core', model='personidentifier')
        self.assertEqual(Version.objects.filter(content_type=person_identifier_content_type).count(), num_of_rows)
        person_has_ext_id = cur_combo['person_has_ext_id']
        has_external_person_col = person_has_ext_id or not (
            cur_combo['is_person_alias_to_person_explicit'] and cur_combo['is_person_identifier_to_person_explicit']
        )
        self.__verify_bulk_records(model_name='Person', has_external=has_external_person_col, num_of_rows=num_of_rows)
        has_external_person_alias_col = cur_combo['person_alias_has_ext_id']
        self.__verify_bulk_records(model_name='PersonAlias', has_external=has_external_person_alias_col,
                                   num_of_rows=num_of_rows)
        has_external_person_identifier_col = cur_combo['person_identifier_has_ext_id']
        self.__verify_bulk_records(model_name='PersonIdentifier', has_external=has_external_person_identifier_col,
                                   num_of_rows=num_of_rows)
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
        self.__verify_integrity_person_by_person(
            response=response,
            cur_combo=cur_combo,
            has_external_person_col=has_external_person_col,
            is_external_person_col_auto=(not person_has_ext_id),
            has_external_person_alias_col=has_external_person_alias_col,
            has_external_person_identifier_col=has_external_person_identifier_col,
            uuid=uuid
        )

    @staticmethod
    def __delete_integrity_subtest_data():
        """ Remove the test data that was added during one sub-test for wholesale import integrity.

        :return: Nothing.
        """
        Version.objects.all().delete()
        getattr(Revision, 'objects').all().delete()
        BulkImport.objects.filter(table_imported_to='Person').delete()
        BulkImport.objects.filter(table_imported_to='PersonAlias').delete()
        BulkImport.objects.filter(table_imported_to='PersonIdentifier').delete()
        PersonAlias.objects.all().delete()
        PersonIdentifier.objects.all().delete()
        Person.objects.all().delete()

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

    @local_test_settings_required
    def test_wholesale_import_add_integrity(self):
        """ Test that data integrity is preserved during "add" imports, including for combinations when:
                (A) Models may or may not have external IDs defined;
                (B) Models may reference foreign keys via PK, name or external ID;
                (C) Models may reference many-to-many fields via PK, name or external ID; and
                (D) Models may reference other models on the same row through explicit references, on the same row
                    through implicit references, or on a different row through explicit references.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import "add" integrity'))
        num_of_rows = 10
        self.__delete_integrity_subtest_data()
        person_class_name = ModelHelper.get_str_for_cls(model_class=Person)
        person_alias_class_name = ModelHelper.get_str_for_cls(model_class=PersonAlias)
        person_identifier_class_name = ModelHelper.get_str_for_cls(model_class=PersonIdentifier)
        external_suffix = WholesaleImport.external_id_suffix
        person_alias_person_col = f'{person_alias_class_name}.person{external_suffix}'
        person_identifier_person_col = f'{person_identifier_class_name}.person{external_suffix}'
        person_ext_id_callable = lambda row_num: f'wholesaletestperson{row_num}'
        # shift rows so that references are not on the same row
        person_mixed_ext_id_callable = lambda row_num: person_ext_id_callable(
            row_num=(row_num + 5) if (row_num + 5) < num_of_rows else (num_of_rows - row_num - 1)
        )
        person_has_ext_id_tuple = (True, False)
        person_alias_has_ext_id_tuple = (True, False)
        person_identifier_has_ext_id_tuple = (True, False)
        person_alias_to_person_tuple = (
            # explicit reference to person with external ID on same CSV row
            (True, person_alias_person_col, person_ext_id_callable),
            # explicit reference to person with external ID on different CSV row
            (True, person_alias_person_col, person_mixed_ext_id_callable),
            # implicit reference to person based on same CSV row
            (False,)
        )
        person_identifier_to_person_tuple = (
            # explicit reference to person with external ID on same CSV row
            (True, person_identifier_person_col, person_ext_id_callable),
            # explicit reference to person with external ID on different CSV row
            (True, person_identifier_person_col, person_mixed_ext_id_callable),
            # implicit reference to person based on same CSV row
            (False,)
        )
        traits_col = f'{person_class_name}.traits'
        traits_by_pk_callable, traits_by_name_callable, traits_by_ext_callable = self.__get_traits_callables()
        traits_tuples = (
            (traits_by_pk_callable, traits_col),
            (traits_by_name_callable, traits_col),
            (traits_by_ext_callable, f'{traits_col}{external_suffix}')
        )
        identifier_type_col = f'{person_identifier_class_name}.person_identifier_type'
        identifier_types_by_pk_callable, identifier_types_by_name_callable, identifier_types_by_ext_callable = \
            self.__get_person_identifier_types_callables()
        identifier_type_tuples = (
            (identifier_types_by_pk_callable, identifier_type_col),
            (identifier_types_by_name_callable, identifier_type_col),
            (identifier_types_by_ext_callable, f'{identifier_type_col}{external_suffix}')
        )
        # cycle through all possible combinations of format for the dummy CSV import
        for product_tuple in product(
                # whether person, person alias, and/or person identifier has external IDs
                person_has_ext_id_tuple, person_alias_has_ext_id_tuple, person_identifier_has_ext_id_tuple,
                # how persons are referenced by person aliases and person identifiers, i.e. through external IDs on the
                # same row, on different rows, through implicit references
                person_alias_to_person_tuple, person_identifier_to_person_tuple,
                # how traits and identifier types are referenced, i.e. by PK, by name or by external ID
                traits_tuples, identifier_type_tuples
        ):
            person_has_ext_id = product_tuple[0]
            person_alias_to_person_ref_tuple = product_tuple[3]
            # can only have explicit reference to person, if person has external ID defined
            is_person_alias_to_person_explicit = person_alias_to_person_ref_tuple[0] and person_has_ext_id
            person_identifier_to_person_ref_tuple = product_tuple[4]
            # can only have explicit reference to person, if person has external ID defined
            is_person_identifier_to_person_explicit = person_identifier_to_person_ref_tuple[0] and person_has_ext_id
            trait_tuple = product_tuple[5]
            identifier_type_tuple = product_tuple[6]
            cur_combo = {
                'person_class_name': person_class_name,
                'person_alias_class_name': person_alias_class_name,
                'person_identifier_class_name': person_identifier_class_name,
                'person_name_col': f'{person_class_name}.name',
                'person_alias_name_col': f'{person_alias_class_name}.name',
                'person_identifier_identifier_col': f'{person_identifier_class_name}.identifier',
                'person_name_callable': lambda row_num: f'wholesaletestpersonname{row_num}',
                'person_alias_name_callable': lambda row_num: f'wholesaletestpersonaliasname{row_num}',
                'person_identifier_identifier_callable':
                    lambda row_num: f'wholesaletestpersonidentifieridentifier{row_num}',
                'person_alias_ext_id_callable': lambda row_num: f'wholesaletestpersonalias{row_num}',
                'person_identifier_ext_id_callable': lambda row_num: f'wholesaletestpersonidentifier{row_num}',
                'person_ext_id_col': f'{person_class_name}.id{external_suffix}',
                'person_alias_ext_id_col': f'{person_alias_class_name}.id{external_suffix}',
                'person_identifier_ext_id_col': f'{person_identifier_class_name}.id{external_suffix}',
                'person_ext_id_callable': person_ext_id_callable,
                'person_has_ext_id': person_has_ext_id,
                'person_alias_has_ext_id': product_tuple[1],
                'person_identifier_has_ext_id': product_tuple[2],
                'is_person_alias_to_person_explicit': is_person_alias_to_person_explicit,
                'person_alias_to_person_col': None if not is_person_alias_to_person_explicit
                else person_alias_to_person_ref_tuple[1],
                'person_alias_to_person_callable': None if not is_person_alias_to_person_explicit
                else person_alias_to_person_ref_tuple[2],
                'is_person_identifier_to_person_explicit': is_person_identifier_to_person_explicit,
                'person_identifier_to_person_col': None if not is_person_identifier_to_person_explicit
                else person_identifier_to_person_ref_tuple[1],
                'person_identifier_to_person_callable': None if not is_person_identifier_to_person_explicit
                else person_identifier_to_person_ref_tuple[2],
                'trait_callable': trait_tuple[0],
                'trait_col': trait_tuple[1],
                'traits_by_pk_callable': traits_by_pk_callable,
                'traits_by_ext_callable': traits_by_ext_callable,
                'identifier_type_callable': identifier_type_tuple[0],
                'identifier_type_col': identifier_type_tuple[1],
                'identifier_types_by_pk_callable': identifier_types_by_pk_callable,
                'identifier_types_by_ext_callable': identifier_types_by_ext_callable,
            }
            self.__print_integrity_subtest_message(cur_combo=cur_combo)
            self.__do_integrity_subtest_import(num_of_rows=num_of_rows, cur_combo=cur_combo)
            self.__verify_integrity_subtest_import(num_of_rows=num_of_rows, cur_combo=cur_combo)
            self.__delete_integrity_subtest_data()
        logger.debug(_('\nSuccessfully finished test for the wholesale import "add" integrity\n\n'))
