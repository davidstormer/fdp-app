from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.apps import apps
from django.utils.timezone import now
from django.db.models import DateTimeField
from inheritable.models import AbstractConfiguration, AbstractSql
from inheritable.tests import AbstractTestCase, local_test_settings_required
from bulk.models import BulkImport
from core.models import Person, Incident, PersonIncident, PersonPayment
from fdpuser.models import FdpUser, FdpOrganization
from supporting.models import Trait, PersonIdentifierType
from sourcing.models import Attachment, AttachmentType, ContentType
from wholesale.models import WholesaleImport, WholesaleImportRecord, ModelHelper
from json import dumps as json_dumps
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class WholesaleTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test that wholesale views are accessible by admin host users only.

    (2) Test wholesale import models allowlist, specifically that:
            (A) Models omitted from allowlist are not available in the dropdown during template generation;
            (B) Models omitted from allowlist cannot be submitted for template generation; and
            (C) Models omitted from allowlist cannot be imported.

    (3) Test wholesale import model fields denylist, specifically that:
            (A) Fields included in denylist are not available in the dropdown during template generation;
            (B) Fields included in denylist cannot be submitted for template generation; and
            (C) Fields included in denylist cannot be imported.

    (4) Test that there are no ambiguous model names across apps relevant to wholesale import.

    (5) Test that internal primary key column is excluded from generated templates.

    (6) ~Add integrity~ moved to slow_tests.py

    (7) Test that imports which are not ready for import, cannot be imported, including when the import:
            (A) Was already started;
            (B) Was already ended; and
            (C) Already has errors.

    (8) Test that boolean values are imported as expected.

    (9) Test that string values are imported as expected.

    (10) Test that date values are imported as expected.

    (11) Test that datetime values are imported as expected.

    (12) Test that JSON values are imported as expected.

    (13) Test that integer values are imported as expected.

    (13) Test that decimal values are imported as expected.

    (14) Test an "add" import with:
            (A) An internal primary key column; and
            (B) Both an internal and an external primary key column.

    (15) Test an "update" import without either internal or external primary key columns.

    (16) Test duplicate columns during an:
            (A) "Add" import; and during an
            (B) "Update" import.

    (17) Test an "update" import with some invalid primary key column values, specifically:
            (A) Missing values; and
            (B) Incorrect values.

    (18) Test an "update" import with some invalid external ID column values, specifically:
            (A) Missing values; and
            (B) Incorrect values.

    (19) Test an "add" import with some invalid external ID values, specifically:
            (A) Missing values.

    (20) Test duplicate external ID values, including for combinations when:
            (A) Import is "add" or "update";
            (B) Duplication exists entirely in CSV template, or between database and CSV template.

    (21) Test setting foreign keys to None during:
            (A) "Add" imports; and
            (B) "Update" imports.

    (22) Test setting many-to-many fields to None during:
            (A) "Add" imports; and
            (B) "Update" imports.

    (23) ~Update integrity~ moved to slow_tests.py

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

    #: Name of field through which boolean values are tested during imports.
    __field_for_bool_test = 'for_admin_only'

    #: Name of field through which string values are tested during imports.
    __field_for_string_test = 'description'

    #: Name of field through which date values are tested during imports.
    __field_for_date_test = 'birth_date_range_start'

    #: Name of field through which JSON values are tested during imports.
    __field_for_json_test = 'known_info'

    #: Name of field through which integer values are tested during imports.
    __field_for_int_test = 'start_year'

    #: Name of field through which integer values are tested during imports.
    __field_for_dec_test = 'base_salary'

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
        # setup URLs reused throughout this class
        self.__template_url = reverse('wholesale:template')
        self.__create_import_url = reverse('wholesale:create_import')
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
        if not AttachmentType.objects.all().exists():
            num_of_attachment_types = AttachmentType.objects.all().count() + 1
            AttachmentType.objects.create(name=f'wholesale_test_attachment_type{num_of_attachment_types}')
        # need at least 2 FDP organizations
        while FdpOrganization.objects.all().count() < 2:
            FdpOrganization.objects.create(name=f'wholesale_test_fdp_org{FdpOrganization.objects.all().count()}')
        # need at least 2 content types
        while ContentType.objects.all().count() < 2:
            ContentType.objects.create(name=f'wholesale_test_content_type{ContentType.objects.all().count()}')
        # need at least 3 traits
        while Trait.objects.all().count() < 3:
            Trait.objects.create(name=f'wholesale_test{Trait.objects.all().count()}')
        # need at least 3 person identifier types
        while PersonIdentifierType.objects.all().count() < 3:
            PersonIdentifierType.objects.create(name=f'wholesale_test{PersonIdentifierType.objects.all().count()}')

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

    @staticmethod
    def __get_unique_external_id():
        """ Retrieves a unique external ID that is not yet recorded in the BulkImport table in the database.

        :return: Unique external ID that is not yet in the database.
        """
        ext_base = 'wholesaletestuniqueexternalid'
        ext_suffix = 1
        while f'{ext_base}{ext_suffix}' in list(BulkImport.objects.all().values_list('pk_imported_from', flat=True)):
            ext_suffix += 1
        unique_external_id = f'{ext_base}{ext_suffix}'
        return unique_external_id

    def __add_three_persons(self, add_external_ids):
        """ Add three persons, each with a unique name, to the database. Optionally add corresponding external IDs for
        each person.

        :param add_external_ids: True if external IDs should be added for each person, false otherwise.
        :return: A tuple:
                    [0] First person instance added to database;
                    [1] Second person instance added to database; and
                    [2] Third person instance added to database.
        """
        first_person = Person.objects.create(name=self.__get_unique_person_name())
        second_person = Person.objects.create(name=self.__get_unique_person_name())
        third_person = Person.objects.create(name=self.__get_unique_person_name())
        if add_external_ids:
            self.__add_external_ids(instances=(first_person, second_person, third_person), class_name='Person')
        return first_person, second_person, third_person

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

    def __get_unique_incident_description(self):
        """ Retrieves a unique incident description that does not exist in the database.

        :return: Unique incident description that does not exist in the database.
        """
        base_unique_incident_description = 'Random description #'
        num_of_incidents = Incident.objects.all().count()
        unique_incident_description = f'{base_unique_incident_description}{num_of_incidents}'
        self.assertNotIn(
            unique_incident_description,
            list(Incident.objects.all().values_list('description', flat=True))
        )
        return unique_incident_description

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

    def __get_boolean_test_csv_content(self, unique_person_name, boolean_value):
        """ Retrieves CSV content to test a particular boolean value during an "add" import.

        :param unique_person_name: Unique person name with which boolean value is associated.
        :param boolean_value: Boolean value tested during import.
        :return: String representing CSV content.
        """
        model = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        newline = self.__csv_lineterminator
        return f'{model}.{self.__field_for_person}{comma}{model}.{self.__field_for_bool_test}{newline}' \
               f'{unique_person_name}{comma}{boolean_value}'

    def __get_string_test_csv_content(self, unique_person_name, string_value):
        """ Retrieves CSV content to test a particular string value during an "add" import.

        :param unique_person_name: Unique person name with which string value is associated.
        :param string_value: String value tested during import.
        :return: String representing CSV content.
        """
        model = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        newline = self.__csv_lineterminator
        return f'{model}.{self.__field_for_person}{comma}{model}.{self.__field_for_string_test}{newline}' \
               f'{unique_person_name}{comma}{string_value}'

    def __get_date_test_csv_content(self, unique_person_name, date_value):
        """ Retrieves CSV content to test a particular date value during an "add" import.

        :param unique_person_name: Unique person name with which date value is associated.
        :param date_value: Date value tested during import.
        :return: String representing CSV content.
        """
        model = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        newline = self.__csv_lineterminator
        return f'{model}.{self.__field_for_person}{comma}{model}.{self.__field_for_date_test}{newline}' \
               f'{unique_person_name}{comma}{date_value}'

    def __get_json_test_csv_content(self, person, incident, json_value):
        """ Retrieves CSV content to test a particular json value during an "add" import.

        :param person: Person linked to the person incident with which the JSON value is associated.
        :param incident: Incident linked to the person incident with which the JSON value is associated.
        :param json_value: JSON value tested during import.
        :return: String representing CSV content.
        """
        model = ModelHelper.get_str_for_cls(model_class=PersonIncident)
        comma = WholesaleImport.csv_delimiter
        newline = self.__csv_lineterminator
        double_quote = WholesaleImport.csv_quotechar
        return f'{model}.person_id{comma}{model}.incident_id{comma}{model}.{self.__field_for_json_test}{newline}' \
               f'{person.pk}{comma}{incident.pk}{comma}{double_quote}{json_value}{double_quote}'

    def __get_int_test_csv_content(self, unique_incident_description, int_value):
        """ Retrieves CSV content to test a particular integer value during an "add" import.

        :param unique_incident_description: Unique incident description with which integer value is associated.
        :param int_value: Integer value tested during import.
        :return: String representing CSV content.
        """
        model = ModelHelper.get_str_for_cls(model_class=Incident)
        comma = WholesaleImport.csv_delimiter
        newline = self.__csv_lineterminator
        return f'{model}.description{comma}{model}.{self.__field_for_int_test}{newline}' \
               f'{unique_incident_description}{comma}{int_value}'

    def __get_dec_test_csv_content(self, unique_person_name, dec_value):
        """ Retrieves CSV content to test a particular decimal value during an "add" import.

        :param unique_person_name: Unique person name with which decimal value is associated.
        :param dec_value: Decimal value tested during import.
        :return: String representing CSV content.
        """
        p = ModelHelper.get_str_for_cls(model_class=Person)
        pp = ModelHelper.get_str_for_cls(model_class=PersonPayment)
        comma = WholesaleImport.csv_delimiter
        newline = self.__csv_lineterminator
        return f'{p}.{self.__field_for_person}{comma}{pp}.{self.__field_for_dec_test}{newline}' \
               f'{unique_person_name}{comma}{dec_value}'

    @staticmethod
    def __get_wholesale_import(filter_kwargs, create_kwargs):
        """ Retrieves a wholesale import record with a particular configuration, if it exists; and creates the record
        if it does not already exist.

        :param filter_kwargs: Dictionary that can be expanded into keyword arguments for filtering the Django queryset
        of wholesale import records.
        :param create_kwargs: Dictionary that can be expanded into keyword arguments to create a wholesale import
        record with a particular configuration. Do not include 'action', 'file' and 'user' attributes as these will
        automatically be set.
        :return: Instance of wholesale import record with a particular configuration.
        """
        if not WholesaleImport.objects.filter(**filter_kwargs).exists():
            return WholesaleImport.objects.create(
                action=WholesaleImport.add_value,
                file=SimpleUploadedFile(name='empty.csv', content=''),
                user=(FdpUser.objects.all().first()).email,
                uuid=WholesaleImport.get_uuid(),
                **create_kwargs
            )
        else:
            return WholesaleImport.objects.filter(**filter_kwargs).order_by('-pk').first()

    def __get_wholesale_ready_for_import(self):
        """ Retrieves a wholesale import record that is in a state where it is ready to be imported.

        :return: Instance of wholesale import record that is ready for import.
        """
        return self.__get_wholesale_import(
            filter_kwargs={'started_timestamp__isnull': True, 'ended_timestamp__isnull': True},
            create_kwargs={}
        )

    def __get_wholesale_imported(self):
        """ Retrieves a wholesale import record that is in a state where it has already been imported.

        :return: Instance of wholesale import record that has already been imported.
        """
        return self.__get_wholesale_import(
            filter_kwargs={'started_timestamp__isnull': False, 'ended_timestamp__isnull': False},
            create_kwargs={'started_timestamp': now(), 'ended_timestamp': now()}
        )

    def __get_start_import_url(self):
        """ Retrieves the "start import" URL for a wholesale import record that is ready for import.

        :return: "Start import" URL for a wholesale import record that is ready for import.
        """
        return reverse('wholesale:start_import', kwargs={'pk': (self.__get_wholesale_ready_for_import()).pk})

    def __get_create_import_post_data(self, action, str_content):
        """ Retrieves the data that can be submitted via POST to create a wholesale import.

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

    def __get_create_import_unchanging_kwargs(self):
        """ Retrieves a dictionary that can be expanded into unchanging keyword arguments
        for _get_response_from_post_request(...) when submitting a POST request to create a wholesale import.

        :return: Dictionary that can be expanded into keyword arguments.
        """
        table = WholesaleImport.get_db_table()
        # every time NEXTVAL(...) is called, the PostgreSQL sequence will increase
        self.wholesale_next_val = \
            AbstractSql.exec_single_val_sql(sql_query=f"SELECT NEXTVAL('{table}_id_seq')", sql_params=[]) + 1
        return {
            'fdp_user': self.__host_admin_user,
            'expected_status_code': 302,
            'login_startswith': reverse('wholesale:start_import', kwargs={'pk': self.wholesale_next_val})
        }

    def __get_start_import_unchanging_kwargs(self):
        """ Retrieves a dictionary that can be expanded into unchanging keyword arguments
        for _get_response_from_post_request(...) when submitting a POST request to start a wholesale import.

        :return: Dictionary that can be expanded into keyword arguments.
        """
        return {
            'fdp_user': self.__host_admin_user,
            'expected_status_code': 302,
            'login_startswith': reverse('wholesale:log', kwargs={'pk': (self.__get_wholesale_ready_for_import()).pk})
        }

    def __create_and_start_import(self, csv_content, action=WholesaleImport.add_value):
        """ Creates and starts a wholesale import based on a template.

        :param csv_content: String representation of the content defining the CSV template to import.
        :param action: Action to take during the import. Use WholesaleImport.add_value or WholesaleImport.update_value.
        :return: Nothing.
        """
        create_kwargs = self.__get_create_import_unchanging_kwargs()
        fdp_user = create_kwargs['fdp_user']
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
        # create the import
        response = self._do_post(
            c=response.client,
            url=self.__create_import_url,
            data=self.__get_create_import_post_data(action=action, str_content=csv_content),
            expected_status_code=create_kwargs['expected_status_code'],
            login_startswith=create_kwargs['login_startswith']
        )
        # navigate to the confirmation page, so that implicit conversion can be performed
        start_url = response.url
        response = self._do_get(c=response.client, url=start_url, expected_status_code=200, login_startswith=None)
        # start the import
        self._do_post(
            c=response.client,
            url=start_url,
            data={},
            expected_status_code=302,
            # self.wholesale_next_val is set in __get_create_import_unchanging_kwargs(...)
            login_startswith=reverse('wholesale:log', kwargs={'pk': self.wholesale_next_val})
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
            self.__template_url,
            self.__create_import_url,
            self.__get_start_import_url(),
            reverse('wholesale:logs'),
            reverse('wholesale:log', kwargs={'pk': (self.__get_wholesale_imported()).pk})
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
                self.__template_url,  # NOT a callable
                {self.__post_models_field: (AbstractConfiguration.models_in_wholesale_allowlist())[0]},
                200,  # expected successful HTTP status code
                None  # login_startswith, NOT a callable
            ),
            (
                self.__create_import_url,  # NOT a callable
                self.__get_create_import_post_data(action=WholesaleImport.add_value, str_content='a,b,c'),
                302,  # expected successful HTTP status code
                self.__get_create_import_unchanging_kwargs  # login_startswith, callable
            ),
            (
                self.__get_start_import_url,  # callable
                {},  # starting an import does not require any data to be submitted
                302,  # expected successful HTTP status code
                self.__get_start_import_unchanging_kwargs  # login_startswith, callable
            ),
        )
        can_user_access_host_admin_only = self.__can_user_access_host_admin_only(fdp_user=fdp_user)
        # cycle through URLs and corresponding POST data
        for post_tuple in post_tuples:
            maybe_callable_url = post_tuple[0]
            post_url = maybe_callable_url if not callable(maybe_callable_url) else maybe_callable_url()
            post_data = post_tuple[1]
            expected_successful_status_code = post_tuple[2]
            expected_status_code = expected_successful_status_code if can_user_access_host_admin_only else 403
            logger.debug(f'Checking POST request for {post_url} with expected status code {expected_status_code}')
            maybe_callable_login_startswith = post_tuple[3]
            login_startswith = maybe_callable_login_startswith if not callable(maybe_callable_login_startswith) \
                else maybe_callable_login_startswith()['login_startswith']
            # note number of imports before POSTing
            num_of_imports = WholesaleImport.objects.all().count()
            # note most recent record that is ready for import
            ready_for_import = self.__get_wholesale_ready_for_import()
            self.assertTrue(ready_for_import.is_ready_for_import)
            self._get_response_from_post_request(
                fdp_user=fdp_user,
                url=post_url,
                expected_status_code=expected_status_code,
                login_startswith=login_startswith,
                post_data=post_data
            )
            # POST created an import
            if maybe_callable_url == self.__create_import_url:
                # import expected to be created
                if expected_status_code == 302:
                    self.assertEqual(num_of_imports + 1, WholesaleImport.objects.all().count())
                # import expected not to be created
                else:
                    self.assertEqual(num_of_imports, WholesaleImport.objects.all().count())
            # POST started an import
            elif maybe_callable_url == self.__get_start_import_url:
                # get updated record from the database
                was_ready_for_import = WholesaleImport.objects.get(pk=ready_for_import.pk)
                # next record that is ready for import
                next_ready_for_import = self.__get_wholesale_ready_for_import()
                # import expected to be started
                if expected_status_code == 302:
                    self.assertNotEqual(next_ready_for_import.pk, ready_for_import.pk)
                    self.assertFalse(was_ready_for_import.is_ready_for_import)
                    self.assertIsNotNone(was_ready_for_import.started_timestamp)
                # import expected not to be started
                else:
                    self.assertEqual(next_ready_for_import.pk, ready_for_import.pk)
                    self.assertTrue(was_ready_for_import.is_ready_for_import)
                    self.assertIsNone(was_ready_for_import.started_timestamp)

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

    def __check_field_in_denylist(self, unique_name, all_unique_names_callable, csv_content, class_name, field_name):
        """ Check the views that are relevant for a field that is in the denylist for wholesale import.

        :param unique_name: Unique name that will identify a dummy model instance to attempt to import through an "add".
        :param all_unique_names_callable: A callable such as __get_all_user_emails(...) or __get_all_person_names(...)
        that will retrieve a list of all unique names against which to compare the instance.
        :param csv_content: CSV content that will be used to attempt to import dummy model instance.
        :param class_name: String representation of model class to which dummy model instance belongs.
        :param field_name: String representation of field to which unique name is attempted to be assigned.
        :return: Nothing.
        """
        self.assertIn(class_name, AbstractConfiguration.models_in_wholesale_allowlist())
        self.assertIn(field_name, AbstractConfiguration.fields_in_wholesale_denylist())
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
        self.__create_and_start_import(csv_content=csv_content)
        self.assertNotIn(unique_name, all_unique_names_callable())
        self.assertEqual(
            f'Field {field_name} is in denylist for wholesale import.',
            (WholesaleImport.objects.all().order_by('-pk').first()).import_errors
        )
        logger.debug(f'Field {field_name} cannot be imported')

    def __check_model_not_in_allowlist(self, unique_name, all_unique_names_callable, csv_content, class_name):
        """ Check the views that are relevant for a model that is not in the allowlist for wholesale import.

        :param unique_name: Unique name that will identify a dummy model instance to attempt to import through an "add".
        :param all_unique_names_callable: A callable such as __get_all_user_emails(...) or __get_all_person_names(...)
        that will retrieve a list of all unique names against which to compare the instance.
        :param csv_content: CSV content that will be used to attempt to import dummy model instance.
        :param class_name: String representation of model class to which dummy model instance belongs.
        :return: Nothing.
        """
        self.assertNotIn(class_name, AbstractConfiguration.models_in_wholesale_allowlist())
        str_response = self._get_response_from_get_request(url=self.__template_url, **self.__unchanging_success_kwargs)
        self.assertNotIn(f'"{class_name}"', str_response)
        logger.debug(f'Model {class_name} is not selectable when generating a template')
        str_response = self._get_response_from_post_request(
            url=self.__template_url,
            **self.__get_template_post_kwargs(model_name=class_name)
        )
        self.assertIn(f'{class_name} is not one of the available choices.', str_response)
        logger.debug(f'Model {class_name} cannot be submitted for template generation')
        self.__create_and_start_import(csv_content=csv_content)
        self.assertNotIn(unique_name, all_unique_names_callable())
        self.assertEqual(
            f'Model {class_name} is not in the allowlist for wholesale import.',
            (WholesaleImport.objects.all().order_by('-pk').first()).import_errors
        )
        logger.debug(f'Model {class_name} cannot be imported')

    def __check_model_in_allowlist_and_field_not_in_denylist(
            self, unique_name, all_unique_names_callable, csv_content, class_name, field_name
    ):
        """ Check the views that are relevant for a model that is in the allowlist and a field that is not in the
        denylist for wholesale import.

        :param unique_name: Unique name that will identify a dummy model instance to attempt to import through an "add".
        :param all_unique_names_callable: A callable such as __get_all_user_emails(...) or __get_all_person_names(...)
        that will retrieve a list of all unique names against which to compare the instance.
        :param csv_content: CSV content that will be used to attempt to import dummy model instance.
        :param class_name: String representation of model class to which dummy model instance belongs.
        :param field_name: String representation of field to which unique name is attempted to be assigned.
        :return: Nothing.
        """
        self.assertIn(class_name, AbstractConfiguration.models_in_wholesale_allowlist())
        self.assertNotIn(field_name, AbstractConfiguration.fields_in_wholesale_denylist())
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
        # create and start import
        self.__create_and_start_import(csv_content=csv_content)
        self.assertIn(unique_name, all_unique_names_callable())
        logger.debug(f'Model {class_name} and field {field_name} can be imported')

    def __check_allowlist_for_person(self, in_allowlist):
        """ Check the views that are relevant for models in the allowlist using dummy import data with the Person model.

        :param in_allowlist: True if the Person model is in the allowlist, false if it is not in the allowlist.
        :return: Nothing.
        """
        unique_person_name = self.__get_unique_person_name()
        unchanging_kwargs = {
            'unique_name': unique_person_name,
            'all_unique_names_callable': self.__get_all_person_names,
            'csv_content': self.__get_person_csv_content(unique_person_name=unique_person_name),
            'class_name': ModelHelper.get_str_for_cls(model_class=Person)
        }
        # person model is in allowlist
        if in_allowlist:
            self.__check_model_in_allowlist_and_field_not_in_denylist(
                field_name=self.__field_for_person,
                **unchanging_kwargs
            )
        # person model is not in allowlist
        else:
            self.__check_model_not_in_allowlist(**unchanging_kwargs)

    def __check_denylist_for_person_name(self, is_in_denylist):
        """ Check the views that are relevant for fields in the denylist using dummy import data with the Person model.

        :param is_in_denylist: True if the name field is in the denylist, false if it is not in the denylist.
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
        # name field is not in denylist
        if not is_in_denylist:
            self.__check_model_in_allowlist_and_field_not_in_denylist(**unchanging_kwargs)
        # name field is in denylist
        else:
            self.__check_field_in_denylist(**unchanging_kwargs)

    def __check_cannot_start_import(self, wholesale_import, finished_kwargs):
        """ Checks that an import, which is not ready for import, cannot be started.

        :param wholesale_import: Instance of wholesale import that is not ready for import.
        :param finished_kwargs: Dictionary that can be expanded into keyword arguments to represent a finished import
        redirection in _get_response_from_get_request(...) and _get_response_from_post_request(...).
        :return: Nothing.
        """
        self.assertFalse(wholesale_import.is_ready_for_import)
        self._get_response_from_get_request(**finished_kwargs)
        self._get_response_from_post_request(post_data={}, **finished_kwargs)

    def __check_can_start_import(self, wholesale_import):
        """ Checks that an import, which is ready for import, can be started.

        :param wholesale_import: Instance of wholesale import that is ready for import.
        :return: Nothing.
        """
        self.assertTrue(wholesale_import.is_ready_for_import)
        self._get_response_from_get_request(
            url=reverse('wholesale:start_import', kwargs={'pk': wholesale_import.pk}),
            **self.__unchanging_success_kwargs
        )

    def __assert_one_wholesale_import_record(self, model_name):
        """ Asserts that the wholesale import was successful with one wholesale import record for the expected model.

        :param model_name: String representation of model that was imported.
        :return: Wholesale import record that was asserted.
        """
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.assertEqual(wholesale_import.import_errors, '')
        self.assertEqual(wholesale_import.imported_rows, 1)
        self.assertEqual(WholesaleImportRecord.objects.filter(wholesale_import=wholesale_import).count(), 1)
        wholesale_import_record = WholesaleImportRecord.objects.get(wholesale_import=wholesale_import)
        self.assertEqual(wholesale_import_record.errors, '')
        self.assertEqual(wholesale_import_record.row_num, 2)
        self.assertEqual(wholesale_import_record.model_name, model_name)
        return wholesale_import_record

    def __assert_person_not_imported(self, wholesale_import, expected_err, unique_person_name):
        """ Asserts that the wholesale import encountered an expected error and that the person defined through the
        import's data template was not imported.

        :param wholesale_import: Instance of wholesale import through which person was attempted to be imported.
        :param expected_err: String representation of the error that is expected.
        :param unique_person_name: Unique name used to identify the person.
        :return: Nothing.
        """
        self.assertEqual(wholesale_import.import_errors, expected_err)
        self.assertEqual(wholesale_import.imported_rows, 0)
        self.assertEqual(WholesaleImportRecord.objects.filter(wholesale_import=wholesale_import).count(), 0)
        self.assertEqual(Person.objects.filter(name=unique_person_name).count(), 0)

    def __check_a_value_for_person_import(self, unique_person_name, field_to_check, expected_field_value):
        """ Checks that a boolean, string or date value that was imported as a single row through an "add" import for a
        single person instance, was imported as expected.

        :param unique_person_name: Unique name of person, through which instance can be identified.
        :param field_to_check: Person field, whose value should be checked.
        :param expected_field_value: Expected value of person field.
        :return: Nothing.
        """
        wholesale_import_record = self.__assert_one_wholesale_import_record(model_name='Person')
        self.assertEqual(Person.objects.filter(name=unique_person_name).count(), 1)
        person = Person.objects.get(name=unique_person_name)
        self.assertEqual(wholesale_import_record.instance_pk, person.pk)
        self.assertEqual(getattr(person, field_to_check), expected_field_value)

    def __check_boolean_value_import(self, boolean_value, expected_boolean_interpretation):
        """ Checks that a boolean value is imported as expected.

        :param boolean_value: Boolean value to import.
        :param expected_boolean_interpretation: Expected interpretation of boolean value. Must be either True or False.
        :return: Nothing.
        """
        unique_person_name = self.__get_unique_person_name()
        self.__create_and_start_import(
            csv_content=self.__get_boolean_test_csv_content(
                unique_person_name=unique_person_name,
                boolean_value=boolean_value
            )
        )
        self.__check_a_value_for_person_import(
            unique_person_name=unique_person_name,
            field_to_check=self.__field_for_bool_test,
            expected_field_value=expected_boolean_interpretation
        )

    def __check_string_value_import(self, string_value):
        """ Checks that a string value is imported as expected.

        :param string_value: String value to import.
        :return: Nothing.
        """
        unique_person_name = self.__get_unique_person_name()
        self.__create_and_start_import(
            csv_content=self.__get_string_test_csv_content(
                unique_person_name=unique_person_name,
                string_value=string_value
            )
        )
        self.__check_a_value_for_person_import(
            unique_person_name=unique_person_name,
            field_to_check=self.__field_for_string_test,
            expected_field_value=string_value
        )

    def __check_date_value_import(self, date_value, expected_date_interpretation):
        """ Checks that a date value is imported as expected.

        :param date_value: Date value to import.
        :param expected_date_interpretation: Expected interpretation of date value.
        :return: Nothing.
        """
        unique_person_name = self.__get_unique_person_name()
        self.__create_and_start_import(
            csv_content=self.__get_date_test_csv_content(
                unique_person_name=unique_person_name,
                date_value=date_value
            )
        )
        self.__check_a_value_for_person_import(
            unique_person_name=unique_person_name,
            field_to_check=self.__field_for_date_test,
            expected_field_value=expected_date_interpretation
        )

    def __check_json_value_import(self, person, incident, json_string, json_object):
        """ Checks that a JSON value is imported as expected.

        :param person: Person linked to person incident for which to import JSON value.
        :param incident: Incident linked to person incident for which to import JSON value.
        :param json_string: String representation of JSON.
        :param json_object: Object representation of JSON.
        :return: Nothing.
        """
        filter_kwargs = {'person': person, 'incident': incident}
        csv_content = self.__get_json_test_csv_content(person=person, incident=incident, json_value=json_string)
        self.__create_and_start_import(csv_content=csv_content)
        wholesale_import_record = self.__assert_one_wholesale_import_record(model_name='PersonIncident')
        self.assertEqual(PersonIncident.objects.filter(**filter_kwargs).count(), 1)
        person_incident = PersonIncident.objects.get(**filter_kwargs)
        self.assertEqual(wholesale_import_record.instance_pk, person_incident.pk)
        self.assertEqual(getattr(person_incident, self.__field_for_json_test), json_object)

    def __check_int_value_import(self, int_value, expected_int_interpretation):
        """ Checks that an integer value is imported as expected.

        :param int_value: Integer value to import.
        :param expected_int_interpretation: Expected interpretation of integer value.
        :return: Nothing.
        """
        unique_incident_description = self.__get_unique_incident_description()
        filter_kwargs = {'description': unique_incident_description}
        self.__create_and_start_import(
            csv_content=self.__get_int_test_csv_content(
                unique_incident_description=unique_incident_description,
                int_value=int_value
            )
        )
        wholesale_import_record = self.__assert_one_wholesale_import_record(model_name='Incident')
        self.assertEqual(Incident.objects.filter(**filter_kwargs).count(), 1)
        incident = Incident.objects.get(**filter_kwargs)
        self.assertEqual(wholesale_import_record.instance_pk, incident.pk)
        self.assertEqual(getattr(incident, self.__field_for_int_test), expected_int_interpretation)

    def __check_dec_value_import(self, dec_value, expected_dec_interpretation):
        """ Checks that a decimal value is imported as expected.

        :param dec_value: Decimal value to import.
        :param expected_dec_interpretation: Expected interpretation of decimal value.
        :return: Nothing.
        """
        unique_person_name = self.__get_unique_person_name()
        filter_kwargs = {'name': unique_person_name}
        self.__create_and_start_import(
            csv_content=self.__get_dec_test_csv_content(
                unique_person_name=unique_person_name,
                dec_value=dec_value
            )
        )
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.assertEqual(wholesale_import.import_errors, '')
        self.assertEqual(wholesale_import.imported_rows, 2)
        self.assertEqual(WholesaleImportRecord.objects.filter(wholesale_import=wholesale_import).count(), 2)
        first_wholesale_import_record = WholesaleImportRecord.objects.filter(wholesale_import=wholesale_import)[0]
        self.assertEqual(first_wholesale_import_record.errors, '')
        self.assertEqual(first_wholesale_import_record.row_num, 2)
        self.assertEqual(first_wholesale_import_record.model_name, 'Person')
        second_wholesale_import_record = WholesaleImportRecord.objects.filter(wholesale_import=wholesale_import)[1]
        self.assertEqual(second_wholesale_import_record.errors, '')
        self.assertEqual(second_wholesale_import_record.row_num, 2)
        self.assertEqual(second_wholesale_import_record.model_name, 'PersonPayment')
        self.assertEqual(Person.objects.filter(**filter_kwargs).count(), 1)
        person = Person.objects.get(**filter_kwargs)
        filter_kwargs = {'person': person}
        self.assertEqual(PersonPayment.objects.filter(**filter_kwargs).count(), 1)
        person_payment = PersonPayment.objects.get(**filter_kwargs)
        self.assertEqual(first_wholesale_import_record.instance_pk, person.pk)
        self.assertEqual(second_wholesale_import_record.instance_pk, person_payment.pk)
        self.assertEqual(getattr(person_payment, self.__field_for_dec_test), expected_dec_interpretation)

    def __check_invalid_pk_import(self, csv_content, expected_error, first_person, second_person, third_person, suffix):
        """ Checks that an "update" import with three people is not successful if some internal or external primary
        key values are invalid.

        :param csv_content: String representation of CSV defining data to import.
        :param expected_error: String representation of exception that is expected.
        :param first_person: First person included in "update" import.
        :param second_person: Second person included in "update" import.
        :param third_person: Third person included in "update" import.
        :param suffix: Suffix that would be added to each person's name, if the import was successful.
        :return: Nothing.
        """
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.update_value)
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.assertEqual(wholesale_import.import_errors, expected_error)
        self.assertEqual(wholesale_import.imported_rows, 0)
        self.assertEqual(Person.objects.filter(name=f'{first_person}{suffix}').count(), 0)
        self.assertEqual(Person.objects.filter(name=f'{second_person}{suffix}').count(), 0)
        self.assertEqual(Person.objects.filter(name=f'{third_person}{suffix}').count(), 0)

    def __check_duplicate_external_id_import(
            self, csv_content, action, expected_error, imported_person_name, duplicate_external_id,
            does_external_id_exist
    ):
        """ Checks that an import with duplicate external IDs is not successful.

        :param csv_content: String representation of CSV defining data to import.
        :param action: Action to take during the import. Use WholesaleImport.add_value or WholesaleImport.update_value.
        :param expected_error: String representation of exception that is expected.
        :param imported_person_name: Name(s) of person(s) that would have been imported if the import were successful.
        :param duplicate_external_id: External ID that is duplicated.
        :param does_external_id_exist: True if the external ID that is duplicated already exists in the database, false
        if it does not exist in the database.
        :return: Nothing.
        """
        self.__create_and_start_import(csv_content=csv_content, action=action)
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.assertEqual(wholesale_import.import_errors, expected_error)
        self.assertEqual(wholesale_import.imported_rows, 0)
        self.assertEqual(WholesaleImportRecord.objects.filter(wholesale_import=wholesale_import).count(), 0)
        self.assertEqual(Person.objects.filter(name=imported_person_name).count(), 0)
        self.assertEqual(BulkImport.objects.filter(pk_imported_from=duplicate_external_id).count(),
                         1 if does_external_id_exist else 0)

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
    def test_wholesale_import_model_allowlist(self):
        """ Test the wholesale import models allowlist, specifically that:
            (A) Models omitted from allowlist are not available in the dropdown during template generation;
            (B) Models omitted from allowlist cannot be submitted for template generation; and
            (C) Models omitted from allowlist cannot be imported.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import models allowlist'))
        person_class_name = ModelHelper.get_str_for_cls(model_class=Person)
        # person model is in allowlist
        logger.debug(f'Starting sub-tests for person model that is in the allowlist')
        self.__check_allowlist_for_person(in_allowlist=True)
        # person model is removed from allowlist
        logger.debug(f'Starting sub-tests for person model that is not in the allowlist')
        with self.settings(
                FDP_WHOLESALE_MODELS_ALLOWLIST=[
                    m for m in AbstractConfiguration.models_in_wholesale_allowlist() if m != person_class_name
                ]
        ):
            self.__check_allowlist_for_person(in_allowlist=False)
        # user model was never in allowlist, and its app is not even checked
        logger.debug(f'Starting sub-tests for user model that was never in the allowlist')
        unique_user_email = self.__get_unique_user_email()
        self.__check_model_not_in_allowlist(
            unique_name=unique_user_email,
            all_unique_names_callable=self.__get_all_user_emails,
            csv_content=self.__get_user_csv_content(unique_user_email=unique_user_email),
            class_name=ModelHelper.get_str_for_cls(model_class=FdpUser)
        )
        logger.debug(_('\nSuccessfully finished test for the wholesale import models allowlist\n\n'))

    @local_test_settings_required
    def test_wholesale_import_field_denylist(self):
        """ Test wholesale import model fields denylist, specifically that:
            (A) Fields included in denylist are not available in the dropdown during template generation;
            (B) Fields included in denylist cannot be submitted for template generation; and
            (C) Fields included in denylist cannot be imported.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import fields denylist'))
        # name field is not in denylist
        logger.debug(f'Starting sub-tests for name field that is not in denylist')
        self.__check_denylist_for_person_name(is_in_denylist=False)
        # name field is added to denylist
        logger.debug(f'Starting sub-tests for name field that is in denylist')
        with self.settings(FDP_WHOLESALE_FIELDS_DENYLIST=['name']):
            self.__check_denylist_for_person_name(is_in_denylist=True)
        logger.debug(_('\nSuccessfully finished test for the wholesale import fields denylist\n\n'))

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
        models_in_wholesale_allowlist = AbstractConfiguration.models_in_wholesale_allowlist()
        for app_to_check in self.__relevant_apps:
            for model_class in list(apps.get_app_config(app_to_check).get_models()):
                model_name = ModelHelper.get_str_for_cls(model_class=model_class)
                if model_name in models_in_wholesale_allowlist:
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
    def test_is_ready_for_import(self):
        """ Test that imports which are not ready for import, cannot be imported, including when the import:
            (A) Was already started;
            (B) Was already ended; and
            (C) Already has errors.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test that imports which are not ready for import, cannot be imported'))
        self._get_response_from_post_request(
            url=self.__create_import_url,
            post_data=self.__get_create_import_post_data(
                action=WholesaleImport.add_value,
                str_content=self.__get_person_csv_content(unique_person_name=self.__get_unique_person_name())
            ),
            **self.__get_create_import_unchanging_kwargs()
        )
        logger.debug(f'Starting an import that is ready for import')
        wholesale_import = WholesaleImport.objects.all().order_by('-pk').first()
        pk = wholesale_import.pk
        finished_kwargs = {
            'fdp_user': self.__host_admin_user,
            'url': reverse('wholesale:start_import', kwargs={'pk': pk}),
            'expected_status_code': 302,
            'login_startswith': reverse('wholesale:log', kwargs={'pk': pk}),
        }
        self.__check_can_start_import(wholesale_import=wholesale_import)
        self._get_response_from_post_request(post_data={}, **finished_kwargs)
        logger.debug(f'Trying to start an import that was already imported')
        wholesale_import = WholesaleImport.objects.get(pk=pk)
        self.__check_cannot_start_import(wholesale_import=wholesale_import, finished_kwargs=finished_kwargs)
        logger.debug(f'Trying to start an import that was started but not ended')
        wholesale_import.ended_timestamp = None
        wholesale_import.full_clean()
        wholesale_import.save()
        self.__check_cannot_start_import(wholesale_import=wholesale_import, finished_kwargs=finished_kwargs)
        logger.debug(f'Trying to start an import that was ended but not started')
        wholesale_import.started_timestamp = None
        wholesale_import.ended_timestamp = now()
        wholesale_import.full_clean()
        wholesale_import.save()
        self.__check_cannot_start_import(wholesale_import=wholesale_import, finished_kwargs=finished_kwargs)
        logger.debug(f'Trying to start an import that already has errors')
        wholesale_import.started_timestamp = now()
        wholesale_import.import_errors = 'Dummy error'
        wholesale_import.full_clean()
        wholesale_import.save()
        self.__check_cannot_start_import(wholesale_import=wholesale_import, finished_kwargs=finished_kwargs)
        # double check that resetting the started and ended timestamps, and clearing the errors, makes the import ready
        wholesale_import.started_timestamp = None
        wholesale_import.ended_timestamp = None
        wholesale_import.import_errors = ''
        wholesale_import.full_clean()
        wholesale_import.save()
        self.__check_can_start_import(wholesale_import=wholesale_import)
        logger.debug(
            _('\nSuccessfully finished test that imports which are not ready for import, cannot be imported\n\n')
        )

    @local_test_settings_required
    def test_boolean_value_import(self):
        """ Test that boolean values are imported as expected.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test to import boolean values'))
        for boolean_value in WholesaleImport.true_booleans:
            logger.debug(f'Checking that "{boolean_value}" is imported as a True boolean value')
            self.__check_boolean_value_import(boolean_value=boolean_value, expected_boolean_interpretation=True)
        for boolean_value in WholesaleImport.false_booleans:
            logger.debug(f'Checking that "{boolean_value}" is imported as a False boolean value')
            self.__check_boolean_value_import(boolean_value=boolean_value, expected_boolean_interpretation=False)
        boolean_field = ModelHelper.get_field(model=Person, field_name=self.__field_for_bool_test)
        default_for_field = boolean_field.get_default()
        logger.debug(f'Checking that a blank value is imported as the '
                     f'default {default_for_field} boolean value for {self.__field_for_bool_test}')
        self.__check_boolean_value_import(boolean_value='', expected_boolean_interpretation=default_for_field)
        logger.debug(_('\nSuccessfully finished test to import boolean values\n\n'))

    @local_test_settings_required
    def test_string_value_import(self):
        """ Test that string values are imported as expected.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test to import string values'))
        for string_value in ('A very random string', ''):
            logger.debug(f'Checking "{string_value}"')
            self.__check_string_value_import(string_value=string_value)
        logger.debug(
            _('\nSuccessfully finished test to import string values\n\n')
        )

    @local_test_settings_required
    def test_date_value_import(self):
        """ Test that date values are imported as expected.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test to import date values'))
        for date_value in ('1970-1-27', '1982-10-1', '1963-05-3', '1954-12-12', '1998-9-08'):
            logger.debug(f'Checking "{date_value}"')
            self.__check_date_value_import(
                date_value=date_value,
                expected_date_interpretation=datetime.strptime(date_value, '%Y-%m-%d').date()
            )
        logger.debug(f'Checking that a blank value is imported as None for {self.__field_for_date_test}')
        self.__check_date_value_import(date_value='', expected_date_interpretation=None)
        logger.debug(
            _('\nSuccessfully finished test to import date values\n\n')
        )

    @local_test_settings_required
    def test_datetime_value_import(self):
        """ Test that datetime values are imported as expected.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test to assert that no datetime values can be imported through wholesale'))
        for relevant_model in ModelHelper.get_relevant_models():
            model_name = ModelHelper.get_str_for_cls(model_class=relevant_model)
            for field_to_check in ModelHelper.get_fields(model=relevant_model):
                field_name = field_to_check.name
                logger.debug(f'Checking model {model_name} and field {field_name}')
                self.assertNotIsInstance(field_to_check, DateTimeField)
        logger.debug(
            _('\nSuccessfully finished test to assert that no datetime values can be imported through wholesale\n\n')
        )

    @local_test_settings_required
    def test_json_value_import(self):
        """ Test that JSON values are imported as expected.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test to import JSON values'))
        person = Person.objects.create(name=self.__get_unique_person_name())
        incident = Incident.objects.create()
        json_object = {
            'list_of_int_values': [1, 2, 3],
            'list_of_decimal_values': [1.5, 2.6, 3.7],
            'list_of_boolean_values': [True, False, True],
            'date_value': '1995-1-1',
            'datetime_value': '1990-7-13 2:45:23',
            'string_value': 'A random string'
        }
        json_string = json_dumps(json_object)
        # the quotechar appears in the JSON
        if WholesaleImport.csv_quotechar in json_string:
            json_string = json_string.replace(WholesaleImport.csv_quotechar, "'")
        # lowercase true should be converted to camelcase True
        lowercase_true = 'true'
        if lowercase_true in json_string:
            json_string = json_string.replace(lowercase_true, 'True')
        # lowercase false should be converted to camelcase False
        lowercase_false = 'false'
        if lowercase_false in json_string:
            json_string = json_string.replace(lowercase_false, 'False')
        logger.debug(f'Checking \'{json_string}\'')
        self.__check_json_value_import(
            person=person,
            incident=incident,
            json_string=json_string,
            json_object=json_object
        )
        PersonIncident.objects.filter(person=person, incident=incident).delete()
        logger.debug(f'Checking that a blank value is imported as None for {self.__field_for_json_test}')
        self.__check_json_value_import(person=person, incident=incident, json_string='', json_object=None)
        logger.debug(_('\nSuccessfully finished test to import JSON values\n\n'))

    @local_test_settings_required
    def test_int_value_import(self):
        """ Test that integer values are imported as expected.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test to import integer values'))
        for int_value in (1995, 0):
            logger.debug(f'Checking "{int_value}"')
            self.__check_int_value_import(int_value=int_value, expected_int_interpretation=int_value)
        int_field = ModelHelper.get_field(model=Incident, field_name=self.__field_for_int_test)
        default_for_field = int_field.get_default()
        logger.debug(f'Checking that a blank value is imported as the '
                     f'default {default_for_field} integer value for {self.__field_for_int_test}')
        self.__check_int_value_import(int_value='', expected_int_interpretation=default_for_field)
        logger.debug(_('\nSuccessfully finished test to import integer values\n\n'))

    @local_test_settings_required
    def test_dec_value_import(self):
        """ Test that decimal values are imported as expected.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test to import decimal values'))
        for dec_value in (123456.78, 0.01, 0.0, 12000.00):
            logger.debug(f'Checking "{dec_value}"')
            self.__check_dec_value_import(dec_value=dec_value, expected_dec_interpretation=Decimal(str(dec_value)))
        logger.debug(f'Checking that a blank value is imported as None for {self.__field_for_dec_test}')
        self.__check_dec_value_import(dec_value='', expected_dec_interpretation=None)
        logger.debug(_('\nSuccessfully finished test to import decimal values\n\n'))

    @local_test_settings_required
    def test_pk_column_during_add_import(self):
        """ Test an "add" import with:
                (A) An internal primary key column; and
                (B) Both an internal and an external primary key column.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for "add" import with a primary key column'))
        unique_person_name = self.__get_unique_person_name()
        expected_err = 'Model Person has an "id" column that is not allowed during adds.'
        p = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        logger.debug(f'Starting sub-test with just the internal primary key column')
        csv_content = f'{p}.id{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'248976{comma}{unique_person_name}'
        self.__create_and_start_import(csv_content=csv_content)
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.__assert_person_not_imported(
            wholesale_import=wholesale_import,
            expected_err=expected_err,
            unique_person_name=unique_person_name
        )
        logger.debug(f'Starting sub-test with both the internal and external primary key columns')
        ext_id = 'wholesaletestpersonexternalidpktest'
        csv_content = f'{p}.id{comma}{p}.id{WholesaleImport.external_id_suffix}{comma}{p}.{self.__field_for_person}' \
                      f'{self.__csv_lineterminator}' \
                      f'87124{comma}{ext_id}{comma}{unique_person_name}'
        self.__create_and_start_import(csv_content=csv_content)
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.__assert_person_not_imported(
            wholesale_import=wholesale_import,
            expected_err=expected_err,
            unique_person_name=unique_person_name
        )
        logger.debug(_('\nSuccessfully finished test for "add" import with a primary key column\n\n'))

    @local_test_settings_required
    def test_no_pk_column_during_update_import(self):
        """ Test an "update" import without either internal or external primary key columns.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for "update" import without any primary key columns'))
        expected_err = 'Model Person does not have an "id" or "id__external" column that is required to update.'
        unique_person_name = self.__get_unique_person_name()
        csv_content = self.__get_person_csv_content(unique_person_name=unique_person_name)
        self.assertNotIn(f'id{WholesaleImport.external_id_suffix}', csv_content)
        self.assertNotIn('id', csv_content)
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.update_value)
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.__assert_person_not_imported(
            wholesale_import=wholesale_import,
            expected_err=expected_err,
            unique_person_name=unique_person_name
        )
        logger.debug(_('\nSuccessfully finished test for "update" import without any primary key columns\n\n'))

    @local_test_settings_required
    def test_duplicate_columns_during_import(self):
        """ Test duplicate columns during an:
                (A) "Add" import; and during an
                (B) "Update" import.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for duplicate columns during an import'))
        unique_person_name = self.__get_unique_person_name()
        expected_err = 'Field name appears more than once for model Person.'
        p = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        logger.debug(f'Starting sub-test for duplicate columns during an "add" import')
        csv_content = f'{p}.{self.__field_for_person}{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{unique_person_name}{comma}{unique_person_name}'
        self.__create_and_start_import(csv_content=csv_content)
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.__assert_person_not_imported(
            wholesale_import=wholesale_import,
            expected_err=expected_err,
            unique_person_name=unique_person_name
        )
        logger.debug(f'Starting sub-test for duplicate columns during an "update" import')
        csv_content = f'{p}.id{comma}{p}.{self.__field_for_person}{comma}{p}.{self.__field_for_person}' \
                      f'{self.__csv_lineterminator}' \
                      f'1{comma}{unique_person_name}{comma}{unique_person_name}'
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.update_value)
        wholesale_import = WholesaleImport.objects.get(pk=self.wholesale_next_val)
        self.__assert_person_not_imported(
            wholesale_import=wholesale_import,
            expected_err=expected_err,
            unique_person_name=unique_person_name
        )
        logger.debug(_('\nSuccessfully finished test for duplicate columns during an import\n\n'))

    @local_test_settings_required
    def test_invalid_pks_during_update_import(self):
        """ Test an "update" import with some invalid primary key column values, specifically:
                (A) Missing values; and
                (B) Incorrect values.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for "update" import with invalid primary key column values'))
        p = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        suffix = 'X'
        first_person, second_person, third_person = self.__add_three_persons(add_external_ids=False)
        unchanging_kwargs = {
            'first_person': first_person,
            'second_person': second_person,
            'third_person': third_person,
            'suffix': suffix
        }
        logger.debug(f'Starting sub-test for missing PKs during an "update" import')
        csv_content = f'{p}.id{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{first_person.pk}{comma}{first_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{comma}{second_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{third_person.pk}{comma}{third_person.name}{suffix}'
        self.__check_invalid_pk_import(
            csv_content=csv_content,
            expected_error='Cannot update Person model in database. At least one record was missing a primary key.',
            **unchanging_kwargs
        )
        logger.debug(f'Starting sub-test for incorrect PKs during an "update" import')
        missing_pk = 1
        while missing_pk in list(Person.objects.all().values_list('id', flat=True)):
            missing_pk += 1
        self.assertFalse(Person.objects.filter(pk=missing_pk).exists())
        expected_error = 'Cannot update models in database. Length of instances found in the database (2) must be ' \
                         'equal to length of corresponding IDs to update (3). This may be caused because some ' \
                         'instances specified for update could not be found in the database.'
        csv_content = f'{p}.id{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{first_person.pk}{comma}{first_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{missing_pk}{comma}{second_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{third_person.pk}{comma}{third_person.name}{suffix}'
        self.__check_invalid_pk_import(csv_content=csv_content, expected_error=expected_error, **unchanging_kwargs)
        logger.debug(_('\nSuccessfully finished test for "update" import with missing primary key column values\n\n'))

    @local_test_settings_required
    def test_invalid_external_ids_during_update_import(self):
        """ Test an "update" import with some invalid external ID values, specifically:
                (A) Missing values; and
                (B) Incorrect values.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for "update" import with invalid external ID values'))
        p = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        external_col = f'id{WholesaleImport.external_id_suffix}'
        suffix = 'X'
        first_person, second_person, third_person = self.__add_three_persons(add_external_ids=True)
        unchanging_kwargs = {
            'first_person': first_person,
            'second_person': second_person,
            'third_person': third_person,
            'suffix': suffix
        }
        first_person_ext_id = getattr(first_person, self.__test_external_id_attr)
        third_person_ext_id = getattr(third_person, self.__test_external_id_attr)
        logger.debug(f'Starting sub-test for missing external IDs during an "update" import')
        csv_content = f'{p}.{external_col}{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{first_person_ext_id}{comma}{first_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{comma}{second_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{third_person_ext_id}{comma}{third_person.name}{suffix}'
        expected_error = \
            'Row 3: record skipped -- Field id__external for model Person expects external PK values but was ' \
            'assigned: \n'
        self.__check_invalid_pk_import(
            csv_content=csv_content,
            expected_error=expected_error,
            **unchanging_kwargs
        )
        logger.debug(f'Starting sub-test for incorrect PKs during an "update" import')
        missing_external_id = self.__get_unique_external_id()
        self.assertFalse(BulkImport.objects.filter(pk_imported_from=f'{missing_external_id}').exists())
        expected_error = 'Cannot update models in database. Length of external ID tuples (3) must be equal to length ' \
                         'of corresponding existing external IDs (2). This may be caused because some external IDs ' \
                         'are not recorded in the database, or are recorded multiple times.'
        csv_content = f'{p}.{external_col}{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{first_person_ext_id}{comma}{first_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{missing_external_id}{comma}{second_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{third_person_ext_id}{comma}{third_person.name}{suffix}'
        self.__check_invalid_pk_import(csv_content=csv_content, expected_error=expected_error, **unchanging_kwargs)
        logger.debug(_('\nSuccessfully finished test for "update" import with invalid external ID values\n\n'))

    @local_test_settings_required
    def test_invalid_external_ids_during_add_import(self):
        """ Test an "add" import with some invalid external ID values, specifically:
                (A) Missing values.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for "add" import with invalid external ID values'))
        p = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        external_col = f'id{WholesaleImport.external_id_suffix}'
        suffix = 'X'
        first_person, second_person, third_person = self.__add_three_persons(add_external_ids=False)
        first_external_id = self.__get_unique_external_id()
        second_external_id = f'{first_external_id}xyz'
        logger.debug(f'Starting sub-test for missing external IDs during an "add" import')
        csv_content = f'{p}.{external_col}{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{first_external_id}{comma}{first_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{comma}{second_person.name}{suffix}{self.__csv_lineterminator}' \
                      f'{second_external_id}{comma}{third_person.name}{suffix}'
        # I don't know if this is right, but I'm going to do this for now until the code has been updated to handle
        # errors differently: -TC
        expected_error = \
            'Row 3: record skipped -- Field id__external for model Person expects external PK values but was ' \
            'assigned:. Cannot update models in database. Length of external ID tuples (2) must be equal to length of ' \
            'corresponding existing external IDs (0). This may be caused because some external IDs are not recorded ' \
            'in the database, or are recorded multiple times.'
        self.__check_invalid_pk_import(
            csv_content=csv_content,
            expected_error=expected_error,
            first_person=first_person,
            second_person=second_person,
            third_person=third_person,
            suffix=suffix
        )
        logger.debug(_('\nSuccessfully finished test for "add" import with invalid external ID values'))

    @local_test_settings_required
    def test_duplicate_external_ids_during_import(self):
        """ Test duplicate external ID values, including for combinations when:
                (A) Import is "add" or "update"; and
                (B) Duplication exists entirely in CSV template, or between database and CSV template.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for duplicate external IDs during imports'))
        p = ModelHelper.get_str_for_cls(model_class=Person)
        comma = WholesaleImport.csv_delimiter
        external_col = f'id{WholesaleImport.external_id_suffix}'
        unique_person_name = self.__get_unique_person_name()
        self.assertFalse(Person.objects.filter(name=unique_person_name).exists())
        unique_external_id = self.__get_unique_external_id()
        # external IDs duplicated in template
        self.assertFalse(BulkImport.objects.filter(pk_imported_from=unique_external_id).exists())
        csv_content = f'{p}.{external_col}{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{unique_external_id}{comma}{unique_person_name}{self.__csv_lineterminator}' \
                      f'{unique_external_id}{comma}{unique_person_name}'
        unchanging_kwargs = {
            'csv_content': csv_content,
            'expected_error': f'The following external IDs appear more than once: 2 X for {unique_external_id}.',
            'imported_person_name': unique_person_name,
            'duplicate_external_id': unique_external_id,
            'does_external_id_exist': False
        }
        logger.debug(f'Starting sub-test for duplicate external IDs in template during an "add" import')
        self.__check_duplicate_external_id_import(action=WholesaleImport.add_value, **unchanging_kwargs)
        logger.debug(f'Starting sub-test for duplicate external IDs in template during an "update" import')
        self.__check_duplicate_external_id_import(action=WholesaleImport.update_value, **unchanging_kwargs)
        # external IDs duplicate between template and database
        person = Person.objects.create(name='Unnamed')
        self.__add_external_ids(instances=(person,), class_name='Person')
        unique_external_id = getattr(person, self.__test_external_id_attr)
        self.assertEqual(BulkImport.objects.filter(pk_imported_from=unique_external_id).count(), 1)
        csv_content = f'{p}.{external_col}{comma}{p}.{self.__field_for_person}{self.__csv_lineterminator}' \
                      f'{unique_external_id}{comma}{unique_person_name}'
        logger.debug(f'Starting sub-test for duplicate external IDs in template and DB during an "add" import')
        self.__check_duplicate_external_id_import(
            action=WholesaleImport.add_value,
            csv_content=csv_content,
            expected_error=f'Cannot add models in database. '
                           f'The following external IDs already exist: {unique_external_id}.',
            imported_person_name=unique_person_name,
            duplicate_external_id=unique_external_id,
            does_external_id_exist=True
        )
        # skip this test since "update" imports reference existing external IDs by default
        logger.debug(f'Skipping sub-test for duplicate external IDs between template and DB during an "update" import')
        logger.debug(_('\nSuccessfully finished test for duplicate external IDs during imports\n\n'))

    @local_test_settings_required
    def test_none_fk_import(self):
        """ Test setting foreign keys to None during:
                (A) "Add" imports; and
                (B) "Update" imports.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for imports setting foreign keys to None'))
        num_of_attachments = Attachment.objects.all().count()
        a = ModelHelper.get_str_for_cls(model_class=Attachment)
        comma = WholesaleImport.csv_delimiter
        csv_content = f'{a}.name{comma}{a}.link{comma}{a}.type{self.__csv_lineterminator}' \
                      f'Unnamed{comma}https://www.google.ca{comma}'
        logger.debug(f'Starting sub-test for setting foreign keys to None during an "add" import')
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.add_value)
        wholesale_import_record = self.__assert_one_wholesale_import_record(model_name='Attachment')
        self.assertEqual(num_of_attachments + 1, Attachment.objects.all().count())
        attachment_pk = wholesale_import_record.instance_pk
        attachment = Attachment.objects.get(pk=attachment_pk)
        self.assertIsNone(attachment.type)
        logger.debug(f'Starting sub-test for setting foreign keys to None during an "update" import')
        attachment.type = AttachmentType.objects.all().first()
        attachment.full_clean()
        attachment.save()
        self.assertIsNotNone((Attachment.objects.get(pk=attachment_pk)).type)
        csv_content = f'{a}.id{comma}{a}.type{self.__csv_lineterminator}{attachment_pk}{comma}'
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.update_value)
        wholesale_import_record = self.__assert_one_wholesale_import_record(model_name='Attachment')
        self.assertEqual(attachment_pk, wholesale_import_record.instance_pk)
        self.assertIsNone((Attachment.objects.get(pk=attachment_pk)).type)
        logger.debug(_('\nSuccessfully finished test for imports setting foreign keys to None\n\n'))

    @local_test_settings_required
    def test_none_m2m_import(self):
        """ Test setting many-to-many fields to None during:
                (A) "Add" imports; and
                (B) "Update" imports.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for imports setting many-to-many fields to None'))
        num_of_attachments = Attachment.objects.all().count()
        a = ModelHelper.get_str_for_cls(model_class=Attachment)
        comma = WholesaleImport.csv_delimiter
        csv_content = f'{a}.name{comma}{a}.link{comma}{a}.fdp_organizations{self.__csv_lineterminator}' \
                      f'Unnamed{comma}https://www.google.ca{comma}'
        logger.debug(f'Starting sub-test for setting many-to-many fields to None during an "add" import')
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.add_value)
        wholesale_import_record = self.__assert_one_wholesale_import_record(model_name='Attachment')
        self.assertEqual(num_of_attachments + 1, Attachment.objects.all().count())
        attachment_pk = wholesale_import_record.instance_pk
        attachment = Attachment.objects.get(pk=attachment_pk)
        self.assertEqual(attachment.fdp_organizations.all().count(), 0)
        logger.debug(f'Starting sub-test for setting many-to-many fields to None during an "update" import')
        all_fdp_organizations = FdpOrganization.objects.all()
        attachment.fdp_organizations.add(all_fdp_organizations[0], all_fdp_organizations[1])
        attachment.full_clean()
        attachment.save()
        self.assertEqual((Attachment.objects.get(pk=attachment_pk)).fdp_organizations.all().count(), 2)
        csv_content = f'{a}.id{comma}{a}.fdp_organizations{self.__csv_lineterminator}{attachment_pk}{comma}'
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.update_value)
        wholesale_import_record = self.__assert_one_wholesale_import_record(model_name='Attachment')
        self.assertEqual(attachment_pk, wholesale_import_record.instance_pk)
        self.assertEqual((Attachment.objects.get(pk=attachment_pk)).fdp_organizations.all().count(), 0)
        logger.debug(_('\nSuccessfully finished test for imports setting many-to-many fields to None\n\n'))
