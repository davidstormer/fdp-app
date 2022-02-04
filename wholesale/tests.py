from unittest import skip

from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.apps import apps
from django.contrib.contenttypes.models import ContentType as content_types_model
from django.utils.timezone import now
from django.db.models import DateTimeField
from inheritable.models import AbstractConfiguration, AbstractSql
from inheritable.tests import AbstractTestCase, local_test_settings_required
from bulk.models import BulkImport
from core.models import Person, PersonAlias, PersonIdentifier, Incident, PersonIncident, PersonPayment
from fdpuser.models import FdpUser, FdpOrganization
from supporting.models import Trait, PersonIdentifierType, ContentIdentifierType
from sourcing.models import Attachment, AttachmentType, Content, ContentIdentifier, ContentCase, ContentType
from .models import WholesaleImport, WholesaleImportRecord, ModelHelper
from reversion.models import Revision, Version
from csv import writer as csv_writer
from json import dumps as json_dumps
from itertools import product
from datetime import datetime
from decimal import Decimal
from io import StringIO
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

    (6) Test that data integrity is preserved during "add" imports, including for combinations when:
            (A) Models may or may not have external IDs defined;
            (B) Models may reference foreign keys via PK, new name, existing name, or external ID;
            (C) Models may reference many-to-many fields via PK, new name, existing name, or external ID; and
            (D) Models may reference other models on the same row through explicit references, on the same row
                through implicit references, or on a different row through explicit references.

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

    (23) Test that data integrity is preserved during "update" imports, including for combinations when:
            (A) Models may have external IDs defined or PKs defined;
            (B) Models may reference foreign keys via PK, new name, existing name, or external ID;
            (C) Models may reference many-to-many fields via PK, new name, existing name, or external ID; and
            (D) Models may reference other models on the same row through explicit references, or on a different row
            through explicit references.

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

    def __add_data_for_update_integrity(
            self, num_of_rows, contents, placeholder_contents, content_identifiers, content_cases
    ):
        """ Adds content, content identifier and content case data used during the "update" import data integrity test.

        :param num_of_rows: Number of rows in CSV data template used in "update" import.
        :param contents: Empty list to which added content will be appended.
        :param placeholder_contents: Empty list to which content intended as placeholder for content case links, will
        be appended.
        :param content_identifiers: Empty list to which added content identifiers will be appended.
        :param content_cases: Empty list to which added content cases will be appended.
        :return: Nothing.
        """
        content_identifier_type = ContentIdentifierType.objects.create(name='wholesale_test_content_identifier_type_0')
        for i in range(0, num_of_rows):
            # content is initially created with blank "type", since __content_type_callable(...) will assign it on the
            # first row, i.e. to have "difference" between initial state and the first update
            # content is initially created with blank "fdp_organizations", since __fdp_orgs_callable(...) will assign
            # it on the first row, i.e. to have "difference" between initial state and the first update
            content = Content.objects.create()
            contents.append(content)
            content_identifiers.append(
                ContentIdentifier.objects.create(
                    content_identifier_type=content_identifier_type,
                    identifier='1234567890',
                    content=content
                )
            )
            content_cases.append(ContentCase.objects.create(content=content))
            placeholder_contents.append(Content.objects.create())
        self.__add_external_ids(instances=contents, class_name='Content')
        self.__add_external_ids(instances=content_identifiers, class_name='ContentIdentifier')
        self.__add_external_ids(instances=content_cases, class_name='ContentCase')

    def __get_traits_callables(self, num_of_rows):
        """ Retrieves the by primary key, by name, and by external ID callables for the Traits model that can be used
        in instances of FieldToImport.

        These callables are used to retrieve the correct trait(s) depending on the row number in the CSV import.

        :param num_of_rows: Total number for rows for which traits will be added.
        :return: A tuple:
                    [0] Traits by primary key callable;
                    [1] Traits that already exist in the database, by name callable;
                    [2] Traits that don't yet exist in the database, by name callable; and
                    [3] Traits by external ID callable.
        """
        trait_class_name = ModelHelper.get_str_for_cls(model_class=Trait)
        three_traits = Trait.objects.all()[:3]
        self.__add_external_ids(instances=three_traits, class_name=trait_class_name)

        def __traits_callable(row_num, attr_name):
            """ Generic callable used to reference traits by PK, name or external ID.

            :param row_num: Row number on which trait(s) appear.
            :param attr_name: Attribute on each trait that is used to reference it.
            :return: Representation of trait(s) that appear on row.
            """
            return '' if row_num % 3 == 0 else (
                getattr(three_traits[0], attr_name) if row_num % 3 == 1
                else f'{getattr(three_traits[1], attr_name)}, {getattr(three_traits[2], attr_name)}'
            )

        return (
            # Callable for traits by PK
            lambda row_num: __traits_callable(row_num=row_num, attr_name='pk'),
            # Callable for traits by name, where records already exist
            lambda row_num: __traits_callable(row_num=row_num, attr_name='name'),
            # Callable for traits by name, where records not yet added
            lambda row_num: f'wholesaletestnewfirsttrait{row_num % num_of_rows}, '
                            f'wholesaletestnewsecondtrait{row_num % num_of_rows}',
            # Callable for traits by external ID
            lambda row_num: __traits_callable(row_num=row_num, attr_name=self.__test_external_id_attr)
        )

    def __get_fdp_orgs_callables(self, num_of_rows):
        """ Retrieves the by primary key, by name, and by external ID callables for the FDP Organizations model that
        can be used in instances of FieldToImport.

        These callables are used to retrieve the correct FDP organizations(s) depending on the row number in the CSV
        import.

        :param num_of_rows: Total number for rows for which FDP organizations will be added.
        :return: A tuple:
                    [0] FDP organizations by primary key callable;
                    [1] FDP organizations that already exist in the database, by name callable;
                    [2] FDP organizations that don't yet exist in the database, by name callable; and
                    [3] FDP organizations by external ID callable.
        """
        fdp_organization_class_name = ModelHelper.get_str_for_cls(model_class=FdpOrganization)
        two_fdp_organizations = FdpOrganization.objects.all()[:2]
        self.__add_external_ids(instances=two_fdp_organizations, class_name=fdp_organization_class_name)

        def __fdp_orgs_callable(row_num, attr_name):
            """ Generic callable used to reference FDP organizations by PK, name or external ID.

            :param row_num: Row number on which FDP organization(s) appear.
            :param attr_name: Attribute on each FDP organization that is used to reference it.
            :return: Representation of FDP organization(s) that appear on row.
            """
            if row_num % 3 == 0:
                return f'{getattr(two_fdp_organizations[1], attr_name)}, {getattr(two_fdp_organizations[0], attr_name)}'
            elif row_num % 3 == 1:
                return getattr(two_fdp_organizations[0], attr_name)
            # leave blank until the end, since when data is created, the value of this attribute will be "blank"
            else:
                return ''

        return (
            # Callable for FDP organizations by PK
            lambda row_num: __fdp_orgs_callable(row_num=row_num, attr_name='pk'),
            # Callable for FDP organizations by name, where records already exist
            lambda row_num: __fdp_orgs_callable(row_num=row_num, attr_name='name'),
            # Callable for FDP organizations by name, where records not yet added
            lambda row_num: f'wholesaletestnewfirstfdporganization{row_num % num_of_rows}, '
                            f'wholesaletestnewsecondfdporganization{row_num % num_of_rows}',
            # Callable for FDP organizations by external ID
            lambda row_num: __fdp_orgs_callable(row_num=row_num, attr_name=self.__test_external_id_attr)
        )

    def __get_person_identifier_types_callables(self, num_of_rows):
        """ Retrieves the by primary key, by name, and by external ID callables for the PersonIdentifierType model
        that can be used in instances of FieldToImport.

        These callables are used to retrieve the correct person identifier type(s) depending on the row number in the
        CSV import.

        :param num_of_rows: Total number for rows for which person identifiers will be added.
        :return: A tuple:
                    [0] Person identifier types by primary key callable;
                    [1] Person identifier types that already exist in the database, by name callable;
                    [2] Person identifier types that don't yet exist in the database, by name callable; and
                    [3] Person identifier types by external ID callable.
        """
        identifier_type_class_name = ModelHelper.get_str_for_cls(model_class=PersonIdentifierType)
        three_identifier_types = PersonIdentifierType.objects.all()[:3]
        self.__add_external_ids(instances=three_identifier_types, class_name=identifier_type_class_name)

        def __identifier_type_callable(row_num, attr_name):
            """ Generic callable used to reference person identifier types by PK, name or external ID.

            :param row_num: Row number on which person identifier type appears.
            :param attr_name: Attribute on each person identifier type that is used to reference it.
            :return: Representation of person identifier type that appears on row.
            """
            return getattr(three_identifier_types[(row_num % 3)], attr_name)

        return (
            # Callable for person identifier type by PK
            lambda row_num: __identifier_type_callable(row_num=row_num, attr_name='pk'),
            # Callable for person identifier type by name, where records already exist
            lambda row_num: __identifier_type_callable(row_num=row_num, attr_name='name'),
            # Callable for person identifier type by name, where records not yet added
            lambda row_num: f'wholesaletestnewtype{row_num % num_of_rows}',
            # Callable for person identifier type by external ID
            lambda row_num: __identifier_type_callable(row_num=row_num, attr_name=self.__test_external_id_attr)
        )

    def __get_content_types_callables(self, num_of_rows):
        """ Retrieves the by primary key, by name, and by external ID callables for the ContentType model
        that can be used in instances of FieldToImport.

        These callables are used to retrieve the correct content type(s) depending on the row number in the CSV import.

        :param num_of_rows: Total number for rows for which content types will be added.
        :return: A tuple:
                    [0] Content types by primary key callable;
                    [1] Content types that already exist in the database, by name callable;
                    [2] Content types that don't yet exist in the database, by name callable; and
                    [3] Content types by external ID callable.
        """
        content_type_class_name = ModelHelper.get_str_for_cls(model_class=ContentType)
        two_content_types = ContentType.objects.all()[:2]
        self.__add_external_ids(instances=two_content_types, class_name=content_type_class_name)

        def __content_type_callable(row_num, attr_name):
            """ Generic callable used to reference content types by PK, name or external ID.

            :param row_num: Row number on which content type appears.
            :param attr_name: Attribute on each content type that is used to reference it.
            :return: Representation of content type that appears on row.
            """
            if row_num % 3 == 0:
                return getattr(two_content_types[0], attr_name)
            elif row_num % 3 == 1:
                return getattr(two_content_types[1], attr_name)
            # leave blank until the end, since when data is created, the value of this attribute will be "blank"
            else:
                return ''

        return (
            # Callable for content type by PK
            lambda row_num: __content_type_callable(row_num=row_num, attr_name='pk'),
            # Callable for content type by name, where records already exist
            lambda row_num: __content_type_callable(row_num=row_num, attr_name='name'),
            # Callable for content type by name, where records not yet added
            lambda row_num: f'wholesaletestnewcontenttype{row_num % num_of_rows}',
            # Callable for content type by external ID
            lambda row_num: __content_type_callable(row_num=row_num, attr_name=self.__test_external_id_attr)
        )

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

    @staticmethod
    def __get_all_trait_names(traits_callable, num_of_rows):
        """ Retrieve all trait names that are expected to be added to the database.

        :param traits_callable: Callable used to generate trait names for each row.
        :param num_of_rows: Total number of rows for which trait names will be generated.
        :return: List of all trait names that are expected to be added to the database.
        """
        trait_names = [
            one_trait.strip() for multiple_traits in [
                unsplit_trait.split(',') for unsplit_trait in [
                    traits_callable(row_num=row_num) for row_num in range(0, num_of_rows)
                ]
            ] for one_trait in multiple_traits
        ]
        return trait_names

    @staticmethod
    def __get_all_person_identifier_type_names(identifier_type_callable, num_of_rows):
        """ Retrieves all person identifier type names that are expected to be added to the database.

        :param identifier_type_callable: Callable used to generate person identifier type names for each row.
        :param num_of_rows: Total number of rows for which person identifier type names will be generated.
        :return: List of all person identifier type names that are expected to be added to the database.
        """
        person_identifier_type_names = [identifier_type_callable(row_num=row_num) for row_num in range(0, num_of_rows)]
        return person_identifier_type_names

    @staticmethod
    def __get_all_fdp_org_names(fdp_orgs_callable, num_of_rows):
        """ Retrieve all FDP organization names that are expected to be added to the database.

        :param fdp_orgs_callable: Callable used to generate FDP organization names for each row.
        :param num_of_rows: Total number of rows for which FDP organization names will be generated.
        :return: List of all FDP organization names that are expected to be added to the database.
        """
        fdp_org_names = [
            one_fdp_org.strip() for multiple_fdp_orgs in [
                unsplit_fdp_org.split(',') for unsplit_fdp_org in [
                    fdp_orgs_callable(row_num=row_num) for row_num in range(0, num_of_rows)
                ]
            ] for one_fdp_org in multiple_fdp_orgs
        ]
        return fdp_org_names

    @staticmethod
    def __get_all_content_type_names(content_type_callable, num_of_rows):
        """ Retrieves all content type names that are expected to be added to the database.

        :param content_type_callable: Callable used to generate content type names for each row.
        :param num_of_rows: Total number of rows for which content type names will be generated.
        :return: List of all content type names that are expected to be added to the database.
        """
        content_type_names = [content_type_callable(row_num=row_num) for row_num in range(0, num_of_rows)]
        return content_type_names

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

    @staticmethod
    def __print_add_integrity_subtest_message(cur_combo):
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
        txt_existing_name = 'name (exists in DB)'
        txt_new_name = 'name (will be added to DB)'
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
            txt_pk if cur_combo['trait_callable'] == cur_combo['traits_by_pk_callable'] else (
                txt_existing_name if cur_combo['trait_callable'] == cur_combo['traits_by_existing_name_callable']
                else txt_new_name
            )
        )
        txt_type = txt_ext if cur_combo['identifier_type_callable'] == cur_combo['identifier_types_by_ext_callable'] \
            else (
                txt_pk if cur_combo['identifier_type_callable'] == cur_combo['identifier_types_by_pk_callable']
                else (
                    txt_existing_name
                    if cur_combo['identifier_type_callable'] == cur_combo['identifier_types_by_existing_name_callable']
                    else txt_new_name
                )
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

    @staticmethod
    def __print_update_integrity_subtest_message(cur_combo):
        """ Print/log a message describing the current import "update" integrity subtest.

        :param cur_combo: Dictionary with relevant variables to generate message.
        :return: Nothing.
        """
        same_row = 'the same row'
        different_row = 'a different row'
        txt_ext = 'external ID'
        txt_pk = 'PK'
        txt_existing_name = 'name (exists in DB)'
        txt_new_name = 'name (will be added to DB)'
        txt_fdp_org = txt_ext if cur_combo['fdp_org_callable'] == cur_combo['fdp_orgs_by_ext_callable'] else (
            txt_pk if cur_combo['fdp_org_callable'] == cur_combo['fdp_orgs_by_pk_callable'] else (
                txt_existing_name if cur_combo['fdp_org_callable'] == cur_combo['fdp_orgs_by_existing_name_callable']
                else txt_new_name
            )
        )
        txt_type = txt_ext if cur_combo['content_type_callable'] == cur_combo['content_types_by_ext_callable'] \
            else (
                txt_pk if cur_combo['content_type_callable'] == cur_combo['content_types_by_pk_callable']
                else (
                    txt_existing_name
                    if cur_combo['content_type_callable'] == cur_combo['content_types_by_existing_name_callable']
                    else txt_new_name
                )
            )
        logger.debug(
            f'Starting sub-test where content is referenced by {txt_pk if cur_combo["content_is_pk_id"] else txt_ext}, '
            f'content identifier is referenced by {txt_pk if cur_combo["content_identifier_is_pk_id"] else txt_ext}, '
            f'content case is referenced by {txt_pk if cur_combo["content_case_is_pk_id"] else txt_ext}, '
            f'content identifier references content '
            f'via {txt_ext if cur_combo["content_identifier_to_content_is_ext"] else txt_pk} '
            f'on {same_row if cur_combo["is_content_identifier_to_content_same_row"] else different_row}, '            
            f'content case references content '
            f'via {txt_ext if cur_combo["content_case_to_content_is_ext"] else txt_pk} '
            f'on {same_row if cur_combo["is_content_case_to_content_same_row"] else different_row}, '
            f'FDP orgs are referenced by {txt_fdp_org}, '
            f'content types are referenced by {txt_type}.'
        )

    def __do_add_integrity_subtest_import(self, num_of_rows, cur_combo):
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
        # create and start import
        self.__create_and_start_import(csv_content=csv_content)

    def __do_update_integrity_subtest_import(self, num_of_rows, cur_combo):
        """ Perform a wholesale "update" import intended for a subtest within the integrity test.

        :param num_of_rows: Number of rows in the CSV template that will be imported.
        :param cur_combo: Dictionary containing variables used to define the import.
        :return: Nothing.
        """
        f = self.FieldToImport
        content_fields = [
            f(callable_for_values=cur_combo['content_id_callable'], column_heading=cur_combo['content_id_col']),
            f(callable_for_values=cur_combo['content_type_callable'], column_heading=cur_combo['content_type_col']),
            f(callable_for_values=cur_combo['content_publication_date_callable'],
              column_heading=cur_combo['content_publication_date_col']),
            f(callable_for_values=cur_combo['fdp_org_callable'], column_heading=cur_combo['fdp_org_col'])
        ]
        content_identifier_fields = [
            f(callable_for_values=cur_combo['content_identifier_id_callable'],
              column_heading=cur_combo['content_identifier_id_col']),
            f(callable_for_values=cur_combo['content_identifier_identifier_callable'],
              column_heading=cur_combo['content_identifier_identifier_col']),
            f(
                callable_for_values=cur_combo['content_identifier_to_content_callable'],
                column_heading=cur_combo['content_identifier_to_content_col']
            )
        ]
        content_case_fields = [
            f(callable_for_values=cur_combo['content_case_id_callable'],
              column_heading=cur_combo['content_case_id_col']),
            f(
                callable_for_values=cur_combo['content_case_to_content_callable'],
                column_heading=cur_combo['content_case_to_content_col']
            ),
            f(callable_for_values=cur_combo['content_case_settlement_amount_callable'],
              column_heading=cur_combo['content_case_settlement_amount_col'])
        ]
        fields_to_import = content_fields + content_identifier_fields + content_case_fields
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
        # create and start import
        self.__create_and_start_import(csv_content=csv_content, action=WholesaleImport.update_value)

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

    def __verify_integrity_content_by_content(self, response, cur_combo):
        """ Verify the integrity of the data imported through an "update" import content-by-content.

        :param response: Http response returned after successful login of user. Contains "client" attribute.
        :param cur_combo: Dictionary containing variables used to define the import.
        :return: Nothing.
        """
        content_class = cur_combo['content_class_name']
        content_identifier_class = cur_combo['content_identifier_class_name']
        content_case_class = cur_combo['content_case_class_name']
        w = WholesaleImportRecord.objects.all()
        f = ['instance_pk', 'row_num']
        all_content_wholesale_records = list(w.filter(model_name=content_class).values(*f))
        all_content_identifier_wholesale_records = list(w.filter(model_name=content_identifier_class).values(*f))
        all_content_case_wholesale_records = list(w.filter(model_name=content_case_class).values(*f))
        b = BulkImport.objects.all()
        f = ['pk_imported_to', 'pk_imported_from']
        all_content_bulk_records = list(b.filter(table_imported_to='Content').values(*f))
        all_content_identifier_bulk_records = list(b.filter(table_imported_to='ContentIdentifier').values(*f))
        all_content_case_bulk_records = list(b.filter(table_imported_to='ContentCase').values(*f))
        all_fdp_org_bulk_records = list(b.filter(table_imported_to='FdpOrganization').values(*f))
        all_content_type_bulk_records = list(b.filter(table_imported_to='ContentType').values(*f))
        for content in Content.objects.all().prefetch_related(
            'content_case', 'content_identifiers', 'fdp_organizations'
        ).select_related('type').exclude(pk__in=[c.pk for c in cur_combo['placeholder_contents']]):
            content_identifiers = content.content_identifiers.all()
            content_case = content.content_case
            self.assertEqual(1, content_identifiers.count())
            self.assertIsNotNone(content_case)
            content_identifier = content_identifiers.first()
            content_wholesale_records = [r for r in all_content_wholesale_records if r['instance_pk'] == content.pk]
            content_identifier_wholesale_records = \
                [r for r in all_content_identifier_wholesale_records if r['instance_pk'] == content_identifier.pk]
            content_case_wholesale_records = \
                [r for r in all_content_case_wholesale_records if r['instance_pk'] == content_case.pk]
            self.assertEqual(1, len(content_wholesale_records))
            self.assertEqual(1, len(content_identifier_wholesale_records))
            self.assertEqual(1, len(content_case_wholesale_records))
            c_kwargs = {'row_num': content_wholesale_records[0]['row_num'] - 1}
            ci_kwargs = {'row_num': content_identifier_wholesale_records[0]['row_num'] - 1}
            cc_kwargs = {'row_num': content_case_wholesale_records[0]['row_num'] - 1}
            self.__verify_one_version(response=response, app_label='sourcing', instance=content)
            self.__verify_one_version(response=response, app_label='sourcing', instance=content_identifier)
            self.__verify_one_version(response=response, app_label='sourcing', instance=content_case)
            content_bulk_records = [r for r in all_content_bulk_records if r['pk_imported_to'] == content.pk]
            self.assertEqual(len(content_bulk_records), 1)
            content_identifier_bulk_records = \
                [r for r in all_content_identifier_bulk_records if r['pk_imported_to'] == content_identifier.pk]
            self.assertEqual(len(content_identifier_bulk_records), 1)
            content_case_bulk_records = \
                [r for r in all_content_case_bulk_records if r['pk_imported_to'] == content_case.pk]
            self.assertEqual(len(content_case_bulk_records), 1)
            self.assertEqual(datetime.strptime(cur_combo['content_publication_date_callable'](**c_kwargs),
                                               WholesaleImport.date_format).date(), content.publication_date)
            fdp_org_callable = cur_combo['fdp_org_callable']
            fdp_orgs_set = set([str(f.pk) for f in content.fdp_organizations.all()])
            if fdp_org_callable == cur_combo['fdp_orgs_by_pk_callable']:
                fdp_orgs_by_pk = str(fdp_org_callable(**c_kwargs))
                fdp_org_pks = fdp_orgs_by_pk.split(',')
                self.assertEqual(fdp_orgs_set, set([f.strip() for f in fdp_org_pks if f.strip() != '']))
            elif fdp_org_callable == cur_combo['fdp_orgs_by_ext_callable']:
                fdp_orgs_by_ext = fdp_org_callable(**c_kwargs)
                fdp_org_exts = fdp_orgs_by_ext.split(',')
                self.assertEqual(
                    set([b['pk_imported_from'] for b in all_fdp_org_bulk_records
                         if str(b['pk_imported_to']) in fdp_orgs_set]),
                    set([f.strip() for f in fdp_org_exts if f.strip() != '']))
            else:
                fdp_orgs_by_name = fdp_org_callable(**c_kwargs)
                fdp_org_names = fdp_orgs_by_name.split(',')
                self.assertEqual(set([f.name for f in content.fdp_organizations.all()]),
                                 set([f.strip() for f in fdp_org_names if f.strip() != '']))
            self.assertEqual(cur_combo['content_identifier_identifier_callable'](**ci_kwargs),
                             content_identifier.identifier)
            self.assertEqual(Decimal(cur_combo['content_case_settlement_amount_callable'](**cc_kwargs)),
                             content_case.settlement_amount)
            content_type_callable = cur_combo['content_type_callable']
            content_type = content.type
            csv_val = content_type_callable(**c_kwargs)
            if content_type is None:
                self.assertEqual(csv_val, '')
            elif content_type_callable == cur_combo['content_types_by_pk_callable']:
                self.assertEqual(content_type.pk, csv_val)
            elif content_type_callable == cur_combo['content_types_by_ext_callable']:
                content_type_bulk_records = \
                    [b for b in all_content_type_bulk_records if b['pk_imported_to'] == content_type.pk]
                self.assertEqual(len(content_type_bulk_records), 1)
                self.assertEqual(content_type_bulk_records[0]['pk_imported_from'], csv_val)
            else:
                self.assertEqual(content.type.name, csv_val)

    def __verify_add_integrity_subtest_import(self, num_of_rows, cur_combo):
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
        fdp_user = (self.__get_create_import_unchanging_kwargs())['fdp_user']
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
        person_content_type = content_types_model.objects.get(app_label='core', model='person')
        self.assertEqual(Version.objects.filter(content_type=person_content_type).count(), num_of_rows)
        person_alias_content_type = content_types_model.objects.get(app_label='core', model='personalias')
        self.assertEqual(Version.objects.filter(content_type=person_alias_content_type).count(), num_of_rows)
        person_identifier_content_type = content_types_model.objects.get(app_label='core', model='personidentifier')
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
        if cur_combo['are_traits_added']:
            trait_names = self.__get_all_trait_names(
                traits_callable=cur_combo['traits_by_new_name_callable'],
                num_of_rows=num_of_rows
            )
            traits = Trait.objects.filter(name__in=trait_names)
            self.assertEqual(len(trait_names), num_of_rows * 2)
            self.assertEqual(len(trait_names), traits.count())
            trait_content_type = content_types_model.objects.get(app_label='supporting', model='trait')
            # two traits added per row, see __get_traits_callables(...)
            self.assertEqual(Version.objects.filter(content_type=trait_content_type).count(), num_of_rows * 2)
            for trait in traits:
                self.__verify_one_version(response=response, app_label='supporting', instance=trait)
        if cur_combo['are_identifier_types_added']:
            identifier_type_names = self.__get_all_person_identifier_type_names(
                identifier_type_callable=cur_combo['identifier_types_by_new_name_callable'],
                num_of_rows=num_of_rows
            )
            identifier_types = PersonIdentifierType.objects.filter(name__in=identifier_type_names)
            self.assertEqual(len(identifier_type_names), num_of_rows)
            self.assertEqual(len(identifier_type_names), identifier_types.count())
            identifier_type_content_type = \
                content_types_model.objects.get(app_label='supporting', model='personidentifiertype')
            self.assertEqual(Version.objects.filter(content_type=identifier_type_content_type).count(), num_of_rows)
            for identifier_type in identifier_types:
                self.__verify_one_version(response=response, app_label='supporting', instance=identifier_type)
        self.__verify_integrity_person_by_person(
            response=response,
            cur_combo=cur_combo,
            has_external_person_col=has_external_person_col,
            is_external_person_col_auto=(not person_has_ext_id),
            has_external_person_alias_col=has_external_person_alias_col,
            has_external_person_identifier_col=has_external_person_identifier_col,
            uuid=uuid
        )

    def __verify_update_integrity_subtest_import(self, num_of_rows, cur_combo):
        """ Verifies data that was imported through a wholesale "update" import for a subtest within the integrity test.

        :param num_of_rows: Number of rows in the CSV template that will be imported.
        :param cur_combo: Dictionary containing variables used to define the import.
        :return: Nothing.
        """
        wholesale_import = WholesaleImport.objects.all().order_by('-pk').first()
        num_of_expected_records = len(wholesale_import.import_models) * num_of_rows
        wholesale_import_records = WholesaleImportRecord.objects.filter(wholesale_import_id=wholesale_import.pk)
        content_class = cur_combo['content_class_name']
        content_identifier_class = cur_combo['content_identifier_class_name']
        content_case_class = cur_combo['content_case_class_name']
        self.assertEqual(wholesale_import.action, WholesaleImport.update_value)
        self.assertEqual(wholesale_import.import_errors, '')
        self.assertEqual(
            set(list(wholesale_import.import_models)), {content_class, content_identifier_class, content_case_class}
        )
        fdp_user = (self.__get_create_import_unchanging_kwargs())['fdp_user']
        self.assertEqual(wholesale_import.user, fdp_user.email)
        self.assertEqual(wholesale_import_records.count(), num_of_expected_records)
        self.assertEqual(wholesale_import_records.filter(errors='').count(), num_of_expected_records)
        self.assertEqual(wholesale_import_records.filter(model_name=content_class).count(), num_of_rows)
        self.assertEqual(wholesale_import_records.filter(model_name=content_identifier_class).count(), num_of_rows)
        self.assertEqual(wholesale_import_records.filter(model_name=content_case_class).count(), num_of_rows)
        self.assertEqual(wholesale_import.error_rows, 0)
        self.assertEqual(wholesale_import.imported_rows, num_of_expected_records)
        self.assertEqual(Content.objects.all().count() - len(cur_combo['placeholder_contents']), num_of_rows)
        self.assertEqual(ContentIdentifier.objects.all().count(), num_of_rows)
        self.assertEqual(ContentCase.objects.all().count(), num_of_rows)
        self.assertEqual(getattr(Revision, 'objects').all().count(), 1)
        revision = getattr(Revision, 'objects').all().first()
        self.assertEqual(revision.user.pk, fdp_user.pk)
        uuid = wholesale_import.uuid
        self.assertIn(uuid, revision.comment)
        content_content_type = content_types_model.objects.get(app_label='sourcing', model='content')
        self.assertEqual(Version.objects.filter(content_type=content_content_type).count(), num_of_rows)
        content_identifier_content_type = \
            content_types_model.objects.get(app_label='sourcing', model='contentidentifier')
        self.assertEqual(Version.objects.filter(content_type=content_identifier_content_type).count(), num_of_rows)
        content_case_content_type = content_types_model.objects.get(app_label='sourcing', model='contentcase')
        self.assertEqual(Version.objects.filter(content_type=content_case_content_type).count(), num_of_rows)
        self.__verify_bulk_records(model_name='Content', has_external=True, num_of_rows=num_of_rows)
        self.__verify_bulk_records(model_name='ContentIdentifier', has_external=True, num_of_rows=num_of_rows)
        self.__verify_bulk_records(model_name='ContentCase', has_external=True, num_of_rows=num_of_rows)
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
        if cur_combo['are_fdp_orgs_added']:
            fdp_org_names = self.__get_all_fdp_org_names(
                fdp_orgs_callable=cur_combo['fdp_orgs_by_new_name_callable'],
                num_of_rows=num_of_rows
            )
            fdp_orgs = FdpOrganization.objects.filter(name__in=fdp_org_names)
            self.assertEqual(len(fdp_org_names), num_of_rows * 2)
            self.assertEqual(len(fdp_org_names), fdp_orgs.count())
            fdp_org_content_type = content_types_model.objects.get(app_label='fdpuser', model='fdporganization')
            # two fdp organizations added per row, see __get_fdp_orgs_callables(...)
            self.assertEqual(Version.objects.filter(content_type=fdp_org_content_type).count(), num_of_rows * 2)
            for fdp_org in fdp_orgs:
                self.__verify_one_version(response=response, app_label='fdpuser', instance=fdp_org)
        if cur_combo['are_content_types_added']:
            content_type_names = self.__get_all_content_type_names(
                content_type_callable=cur_combo['content_types_by_new_name_callable'],
                num_of_rows=num_of_rows
            )
            content_types = ContentType.objects.filter(name__in=content_type_names)
            self.assertEqual(len(content_type_names), num_of_rows)
            self.assertEqual(len(content_type_names), content_types.count())
            content_type_content_type = \
                content_types_model.objects.get(app_label='supporting', model='contenttype')
            self.assertEqual(Version.objects.filter(content_type=content_type_content_type).count(), num_of_rows)
            for content_type in content_types:
                self.__verify_one_version(response=response, app_label='supporting', instance=content_type)
        self.__verify_integrity_content_by_content(response=response, cur_combo=cur_combo)

    @classmethod
    def __delete_add_integrity_subtest_data(cls, traits_callable, identifier_types_callable, num_of_rows):
        """ Remove the test data that was added during one sub-test for wholesale "add" import integrity.

        :param traits_callable: Callable used to generate trait names by row number. Will be None, if no new trait
        records were added to the database.
        :param identifier_types_callable: Callable used to generate person identifier type names by row number. Will be
        None, if no new person identifier type records were added to the database.
        :param num_of_rows: Number of rows in the imported CSV template.
        :return: Nothing.
        """
        WholesaleImportRecord.objects.all().delete()
        WholesaleImport.objects.all().delete()
        Version.objects.all().delete()
        getattr(Revision, 'objects').all().delete()
        BulkImport.objects.filter(table_imported_to='Person').delete()
        BulkImport.objects.filter(table_imported_to='PersonAlias').delete()
        BulkImport.objects.filter(table_imported_to='PersonIdentifier').delete()
        PersonAlias.objects.all().delete()
        PersonIdentifier.objects.all().delete()
        Person.objects.all().delete()
        # only remove traits that were added by name to the database
        if traits_callable is not None:
            trait_names = cls.__get_all_trait_names(traits_callable=traits_callable, num_of_rows=num_of_rows)
            Trait.objects.filter(name__in=trait_names).delete()
        # only remove person identifier types that were added by name to the database
        if identifier_types_callable:
            identifier_type_names = cls.__get_all_person_identifier_type_names(
                identifier_type_callable=identifier_types_callable,
                num_of_rows=num_of_rows
            )
            PersonIdentifierType.objects.filter(name__in=identifier_type_names).delete()

    @classmethod
    def __delete_update_integrity_subtest_data(
            cls, fdp_orgs_callable, content_types_callable, num_of_rows, placeholder_contents
    ):
        """ Remove the test data that was added during one sub-test for wholesale "update" import integrity.

        :param fdp_orgs_callable: Callable used to generate FDP organization names by row number.
        Will be None, if no new FDP organization records were added to the database.
        :param content_types_callable: Callable used to generate content type names by row number. Will be None, if no
        new content type records were added to the database.
        :param num_of_rows: Number of rows in the imported CSV template.
        :param placeholder_contents: List of content that is used as a placeholder for content case links.
        :return: Nothing.
        """
        # link content cases to placeholder contents to avoid the IntegrityError that may occur when shifting
        # OneToOneField values through bulk_update(...), such as:
        # IntegrityError: duplicate key value violates unique constraint "fdp_content_case_content_id_key"
        content_cases = [content_case for content_case in ContentCase.objects.all()]
        for i, content_case in enumerate(content_cases):
            content_case.content = placeholder_contents[i]
        ContentCase.objects.bulk_update(content_cases, ('content',))
        WholesaleImportRecord.objects.all().delete()
        WholesaleImport.objects.all().delete()
        Version.objects.all().delete()
        getattr(Revision, 'objects').all().delete()
        # only remove FDP organizations that were added by name to the database
        if fdp_orgs_callable is not None:
            fdp_org_names = cls.__get_all_fdp_org_names(fdp_orgs_callable=fdp_orgs_callable, num_of_rows=num_of_rows)
            FdpOrganization.objects.filter(name__in=fdp_org_names).delete()
        # only remove content types that were added by name to the database
        if content_types_callable:
            content_type_names = cls.__get_all_content_type_names(
                content_type_callable=content_types_callable,
                num_of_rows=num_of_rows
            )
            ContentType.objects.filter(name__in=content_type_names).delete()

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

    @skip('Runs too slow, move to slow_test_*.py and document how to run separately')
    def test_wholesale_import_add_integrity(self):
        """ Test that data integrity is preserved during "add" imports, including for combinations when:
            (A) Models may or may not have external IDs defined;
            (B) Models may reference foreign keys via PK, new name, existing name, or external ID;
            (C) Models may reference many-to-many fields via PK, new name, existing name, or external ID; and
            (D) Models may reference other models on the same row through explicit references, on the same row
                through implicit references, or on a different row through explicit references.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import "add" integrity'))
        num_of_rows = 10
        row_kwargs = {'num_of_rows': num_of_rows}
        self.__delete_add_integrity_subtest_data(traits_callable=None, identifier_types_callable=None, **row_kwargs)
        person_class_name = ModelHelper.get_str_for_cls(model_class=Person)
        person_alias_class_name = ModelHelper.get_str_for_cls(model_class=PersonAlias)
        person_identifier_class_name = ModelHelper.get_str_for_cls(model_class=PersonIdentifier)
        external_suffix = WholesaleImport.external_id_suffix
        person_alias_person_col = f'{person_alias_class_name}.person{external_suffix}'
        person_identifier_person_col = f'{person_identifier_class_name}.person{external_suffix}'

        def __person_ext_id_callable(row_num):
            """ Callable used to reference persons by external ID that appear on the same row as the referencing model
            instance.

            :param row_num: Row number on which persons appear.
            :return: External ID for person appearing on row.
            """
            return f'wholesaletestperson{row_num}'

        def __person_mixed_ext_id_callable(row_num):
            """ Callable used to reference persons by external ID that appear on a row that is different than the one
            where the referencing model instance exists.

            :param row_num: Row number on which referencing model instance appears.
            :return: External ID for person.
            """
            return __person_ext_id_callable(
                row_num=(row_num + 5) if (row_num + 5) < num_of_rows else (num_of_rows - row_num - 1)
            )

        person_has_ext_id_tuple = (True, False)
        person_alias_has_ext_id_tuple = (True, False)
        person_identifier_has_ext_id_tuple = (True, False)
        person_alias_to_person_tuple = (
            # explicit reference to person with external ID on same CSV row
            (True, person_alias_person_col, __person_ext_id_callable),
            # explicit reference to person with external ID on different CSV row
            (True, person_alias_person_col, __person_mixed_ext_id_callable),
            # implicit reference to person based on same CSV row
            (False,)
        )
        person_identifier_to_person_tuple = (
            # explicit reference to person with external ID on same CSV row
            (True, person_identifier_person_col, __person_ext_id_callable),
            # explicit reference to person with external ID on different CSV row
            (True, person_identifier_person_col, __person_mixed_ext_id_callable),
            # implicit reference to person based on same CSV row
            (False,)
        )
        traits_col = f'{person_class_name}.traits'
        traits_by_pk_callable, traits_by_existing_name_callable, traits_by_new_name_callable, traits_by_ext_callable = \
            self.__get_traits_callables(**row_kwargs)
        traits_tuples = (
            (traits_by_pk_callable, traits_col),
            (traits_by_existing_name_callable, traits_col),
            (traits_by_new_name_callable, traits_col),
            (traits_by_ext_callable, f'{traits_col}{external_suffix}')
        )
        identifier_type_col = f'{person_identifier_class_name}.person_identifier_type'
        identifier_types_by_pk_callable, identifier_types_by_existing_name_callable, \
            identifier_types_by_new_name_callable, identifier_types_by_ext_callable = \
            self.__get_person_identifier_types_callables(**row_kwargs)
        identifier_type_tuples = (
            (identifier_types_by_pk_callable, identifier_type_col),
            (identifier_types_by_existing_name_callable, identifier_type_col),
            (identifier_types_by_new_name_callable, identifier_type_col),
            (identifier_types_by_ext_callable, f'{identifier_type_col}{external_suffix}')
        )
        # cycle through all possible combinations of format for the dummy CSV import
        for product_tuple in product(
                # whether person, person alias, and/or person identifier has external IDs
                person_has_ext_id_tuple, person_alias_has_ext_id_tuple, person_identifier_has_ext_id_tuple,
                # how persons are referenced by person aliases and person identifiers, i.e. through external IDs on the
                # same row, on different rows, through implicit references
                person_alias_to_person_tuple, person_identifier_to_person_tuple,
                # how traits and identifier types are referenced, i.e. by PK, by existing name, by new name, or by
                # external ID
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
            trait_callable = trait_tuple[0]
            identifier_type_tuple = product_tuple[6]
            identifier_type_callable = identifier_type_tuple[0]
            are_traits_added = (trait_callable == traits_by_new_name_callable)
            are_identifier_types_added = (identifier_type_callable == identifier_types_by_new_name_callable)
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
                'person_ext_id_callable': __person_ext_id_callable,
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
                'trait_callable': trait_callable,
                'trait_col': trait_tuple[1],
                'traits_by_pk_callable': traits_by_pk_callable,
                'traits_by_ext_callable': traits_by_ext_callable,
                'traits_by_existing_name_callable': traits_by_existing_name_callable,
                'traits_by_new_name_callable': traits_by_new_name_callable,
                'identifier_type_callable': identifier_type_callable,
                'identifier_type_col': identifier_type_tuple[1],
                'identifier_types_by_pk_callable': identifier_types_by_pk_callable,
                'identifier_types_by_ext_callable': identifier_types_by_ext_callable,
                'identifier_types_by_existing_name_callable': identifier_types_by_existing_name_callable,
                'identifier_types_by_new_name_callable': identifier_types_by_new_name_callable,
                'are_traits_added': are_traits_added,
                'are_identifier_types_added': are_identifier_types_added
            }
            self.__print_add_integrity_subtest_message(cur_combo=cur_combo)
            self.__do_add_integrity_subtest_import(num_of_rows=num_of_rows, cur_combo=cur_combo)
            self.__verify_add_integrity_subtest_import(num_of_rows=num_of_rows, cur_combo=cur_combo)
            self.__delete_add_integrity_subtest_data(
                traits_callable=traits_by_new_name_callable if are_traits_added else None,
                identifier_types_callable=identifier_types_by_new_name_callable if are_identifier_types_added else None,
                **row_kwargs
            )
        logger.debug(_('\nSuccessfully finished test for the wholesale import "add" integrity\n\n'))

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

    @skip('Runs too slow, move to slow_test_*.py and document how to run separately')
    def test_wholesale_import_update_integrity(self):
        """ Test that data integrity is preserved during "update" imports, including for combinations when:
            (A) Models may have external IDs defined or PKs defined;
            (B) Models may reference foreign keys via PK, new name, existing name, or external ID;
            (C) Models may reference many-to-many fields via PK, new name, existing name, or external ID; and
            (D) Models may reference other models on the same row through explicit references, or on a different row
            through explicit references.

        :return: Nothing.
        """
        logger.debug(_('\nStarting test for the wholesale import "update" integrity'))
        num_of_rows = 10
        row_kwargs = {'num_of_rows': num_of_rows}
        contents = []
        # used only to reset content case links
        placeholder_contents = []
        content_identifiers = []
        content_cases = []
        self.__add_data_for_update_integrity(
            contents=contents,
            placeholder_contents=placeholder_contents,
            content_identifiers=content_identifiers,
            content_cases=content_cases,
            **row_kwargs
        )

        content_class_name = ModelHelper.get_str_for_cls(model_class=Content)
        content_identifier_class_name = ModelHelper.get_str_for_cls(model_class=ContentIdentifier)
        content_case_class_name = ModelHelper.get_str_for_cls(model_class=ContentCase)
        external_suffix = WholesaleImport.external_id_suffix
        content_identifier_content_col = f'{content_identifier_class_name}.content'
        content_case_content_col = f'{content_case_class_name}.content'

        def __content_pk_callable(row_num):
            """ Callable used to reference content by primary key that appear on the same row as the referencing model
            instance.

            :param row_num: Row number on which content appear.
            :return: Primary key for content appearing on row.
            """
            return (contents[row_num]).pk

        def __content_mixed_pk_callable(row_num):
            """ Callable used to reference content by primary key that appear on a row that is different than the one
            where the referencing model instance exists.

            :param row_num: Row number on which referencing model instance appears.
            :return: Primary key for content.
            """
            return __content_pk_callable(
                row_num=(row_num + 2) if (row_num + 2) < num_of_rows else (num_of_rows - row_num - 1)
            )

        def __content_ext_id_callable(row_num):
            """ Callable used to reference content by external ID that appear on the same row as the referencing model
            instance.

            :param row_num: Row number on which content appear.
            :return: External ID for content appearing on row.
            """
            return getattr(contents[row_num], self.__test_external_id_attr)

        def __content_mixed_ext_id_callable(row_num):
            """ Callable used to reference content by external ID that appear on a row that is different than the one
            where the referencing model instance exists.

            :param row_num: Row number on which referencing model instance appears.
            :return: External ID for content.
            """
            return __content_ext_id_callable(
                row_num=(row_num + 3) if (row_num + 3) < num_of_rows else (num_of_rows - row_num - 1)
            )

        content_is_pk_id_tuple = (True, False)
        content_identifier_is_pk_id_tuple = (True, False)
        content_case_is_pk_id_tuple = (True, False)
        content_identifier_to_content_tuple = (
            # explicit reference to content with external ID on same CSV row
            (False, f'{content_identifier_content_col}{external_suffix}', __content_ext_id_callable),
            # explicit reference to content with external ID on different CSV row
            (False, f'{content_identifier_content_col}{external_suffix}', __content_mixed_ext_id_callable),
            # explicit reference to content with primary key on same CSV row
            (True, content_identifier_content_col, __content_pk_callable),
            # explicit reference to content with primary key on different CSV row
            (True, content_identifier_content_col, __content_mixed_pk_callable),
        )
        content_case_to_content_tuple = (
            # explicit reference to content with external ID on same CSV row
            (False, f'{content_case_content_col}{external_suffix}', __content_ext_id_callable),
            # explicit reference to content with external ID on different CSV row
            (False, f'{content_case_content_col}{external_suffix}', __content_mixed_ext_id_callable),
            # explicit reference to content with primary key on same CSV row
            (True, content_case_content_col, __content_pk_callable),
            # explicit reference to content with primary key on different CSV row
            (True, content_case_content_col, __content_mixed_pk_callable),
        )
        fdp_orgs_col = f'{content_class_name}.fdp_organizations'
        fdp_orgs_by_pk_callable, fdp_orgs_by_existing_name_callable, \
            fdp_orgs_by_new_name_callable, fdp_orgs_by_ext_callable = self.__get_fdp_orgs_callables(**row_kwargs)
        fdp_orgs_tuples = (
            (fdp_orgs_by_pk_callable, fdp_orgs_col),
            (fdp_orgs_by_existing_name_callable, fdp_orgs_col),
            (fdp_orgs_by_new_name_callable, fdp_orgs_col),
            (fdp_orgs_by_ext_callable, f'{fdp_orgs_col}{external_suffix}')
        )
        content_type_col = f'{content_class_name}.type'
        content_types_by_pk_callable, content_types_by_existing_name_callable, \
            content_types_by_new_name_callable, content_types_by_ext_callable = \
            self.__get_content_types_callables(**row_kwargs)
        content_type_tuples = (
            (content_types_by_pk_callable, content_type_col),
            (content_types_by_existing_name_callable, content_type_col),
            (content_types_by_new_name_callable, content_type_col),
            (content_types_by_ext_callable, f'{content_type_col}{external_suffix}')
        )
        # cycle through all possible combinations of format for the dummy CSV import
        for product_tuple in product(
                # whether the existing content, content identifier and content case is referenced by external IDs or PKs
                content_is_pk_id_tuple, content_identifier_is_pk_id_tuple, content_case_is_pk_id_tuple,
                # how content are referenced by content identifiers and content cases, i.e. through external IDs on the
                # same row or on different rows, or through PKs on the same row or on different rows
                content_case_to_content_tuple, content_identifier_to_content_tuple,
                # how FDP organizations and content types are referenced, i.e. by PK, by existing name, by new name,
                # or by external ID
                fdp_orgs_tuples, content_type_tuples
        ):
            content_is_pk_id = product_tuple[0]
            content_id_col = f"{content_class_name}.id{'' if content_is_pk_id else external_suffix}"
            content_id_callable = __content_pk_callable if content_is_pk_id else __content_ext_id_callable
            content_identifier_is_pk_id = product_tuple[1]
            content_identifier_id_col = f"{content_identifier_class_name}.id" \
                                        f"{'' if content_identifier_is_pk_id else external_suffix}"
            content_case_is_pk_id = product_tuple[2]
            content_case_id_col = f"{content_case_class_name}.id{'' if content_case_is_pk_id else external_suffix}"
            content_case_to_content_ref_tuple = product_tuple[3]
            content_case_to_content_callable = content_case_to_content_ref_tuple[2]
            is_content_case_to_content_same_row = \
                (content_case_to_content_callable == __content_mixed_pk_callable) \
                or (content_case_to_content_callable == __content_mixed_ext_id_callable)
            content_identifier_to_content_ref_tuple = product_tuple[4]
            content_identifier_to_content_callable = content_identifier_to_content_ref_tuple[2]
            is_content_identifier_to_content_same_row = \
                (content_identifier_to_content_callable == __content_mixed_pk_callable) \
                or (content_identifier_to_content_callable == __content_mixed_ext_id_callable)
            fdp_org_tuple = product_tuple[5]
            fdp_org_callable = fdp_org_tuple[0]
            content_type_tuple = product_tuple[6]
            content_type_callable = content_type_tuple[0]
            are_fdp_orgs_added = (fdp_org_callable == fdp_orgs_by_new_name_callable)
            are_content_types_added = (content_type_callable == content_types_by_new_name_callable)
            cur_combo = {
                'placeholder_contents': placeholder_contents,
                'content_is_pk_id': content_is_pk_id,
                'content_id_col': content_id_col,
                'content_id_callable': content_id_callable,
                'content_identifier_is_pk_id': content_identifier_is_pk_id,
                'content_identifier_id_col': content_identifier_id_col,
                'content_case_is_pk_id': content_case_is_pk_id,
                'content_case_id_col': content_case_id_col,
                'content_class_name': content_class_name,
                'content_identifier_class_name': content_identifier_class_name,
                'content_case_class_name': content_case_class_name,
                'content_publication_date_col': f'{content_class_name}.publication_date',
                'content_identifier_identifier_col': f'{content_identifier_class_name}.identifier',
                'content_case_settlement_amount_col': f'{content_case_class_name}.settlement_amount',
                'content_publication_date_callable': lambda row_num: f'2020-05-{(row_num % 30) + 1}',
                'content_identifier_identifier_callable': lambda row_num: f'ABCDEF{row_num}',
                'content_case_settlement_amount_callable': lambda row_num: f'{row_num}00.00',
                'content_identifier_id_callable': lambda row_num: getattr(
                    content_identifiers[row_num],
                    'pk' if content_identifier_is_pk_id else self.__test_external_id_attr
                ),
                'content_case_id_callable': lambda row_num: getattr(
                    content_cases[row_num],
                    'pk' if content_case_is_pk_id else self.__test_external_id_attr
                ),
                'content_identifier_to_content_is_ext': content_identifier_to_content_ref_tuple[0],
                'content_identifier_to_content_col': content_identifier_to_content_ref_tuple[1],
                'content_identifier_to_content_callable': content_identifier_to_content_callable,
                'is_content_identifier_to_content_same_row': is_content_identifier_to_content_same_row,
                'content_case_to_content_is_ext': content_case_to_content_ref_tuple[0],
                'content_case_to_content_col': content_case_to_content_ref_tuple[1],
                'content_case_to_content_callable': content_case_to_content_callable,
                'is_content_case_to_content_same_row': is_content_case_to_content_same_row,
                'fdp_org_callable': fdp_org_callable,
                'fdp_org_col': fdp_org_tuple[1],
                'fdp_orgs_by_pk_callable': fdp_orgs_by_pk_callable,
                'fdp_orgs_by_ext_callable': fdp_orgs_by_ext_callable,
                'fdp_orgs_by_existing_name_callable': fdp_orgs_by_existing_name_callable,
                'fdp_orgs_by_new_name_callable': fdp_orgs_by_new_name_callable,
                'content_type_callable': content_type_callable,
                'content_type_col': content_type_tuple[1],
                'content_types_by_pk_callable': content_types_by_pk_callable,
                'content_types_by_ext_callable': content_types_by_ext_callable,
                'content_types_by_existing_name_callable': content_types_by_existing_name_callable,
                'content_types_by_new_name_callable': content_types_by_new_name_callable,
                'are_fdp_orgs_added': are_fdp_orgs_added,
                'are_content_types_added': are_content_types_added
            }
            self.__print_update_integrity_subtest_message(cur_combo=cur_combo)
            self.__do_update_integrity_subtest_import(num_of_rows=num_of_rows, cur_combo=cur_combo)
            self.__verify_update_integrity_subtest_import(num_of_rows=num_of_rows, cur_combo=cur_combo)
            self.__delete_update_integrity_subtest_data(
                fdp_orgs_callable=fdp_orgs_by_new_name_callable if are_fdp_orgs_added else None,
                content_types_callable=content_types_by_new_name_callable if are_content_types_added else None,
                placeholder_contents=placeholder_contents,
                **row_kwargs
            )
        logger.debug(_('\nSuccessfully finished test for the wholesale import "update" integrity\n\n'))
