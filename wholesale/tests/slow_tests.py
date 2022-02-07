from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.contenttypes.models import ContentType as content_types_model
from inheritable.models import AbstractSql
from inheritable.tests import AbstractTestCase
from bulk.models import BulkImport
from core.models import Person, PersonAlias, PersonIdentifier
from fdpuser.models import FdpUser, FdpOrganization
from supporting.models import Trait, PersonIdentifierType, ContentIdentifierType, AttachmentType
from sourcing.models import Content, ContentIdentifier, ContentCase, ContentType
from wholesale.models import WholesaleImport, WholesaleImportRecord, ModelHelper
from reversion.models import Revision, Version
from csv import writer as csv_writer
from json import dumps as json_dumps
from itertools import product
from datetime import datetime
from decimal import Decimal
from io import StringIO
import logging

logger = logging.getLogger(__name__)


class IntegrityWholesaleTestCase(AbstractTestCase):
    """ Performs following tests:

    Test that data integrity is preserved during "add" imports, including for combinations when:
            (A) Models may or may not have external IDs defined;
            (B) Models may reference foreign keys via PK, new name, existing name, or external ID;
            (C) Models may reference many-to-many fields via PK, new name, existing name, or external ID; and
            (D) Models may reference other models on the same row through explicit references, on the same row
                through implicit references, or on a different row through explicit references.

    Test that data integrity is preserved during "update" imports, including for combinations when:
            (A) Models may have external IDs defined or PKs defined;
            (B) Models may reference foreign keys via PK, new name, existing name, or external ID;
            (C) Models may reference many-to-many fields via PK, new name, existing name, or external ID; and
            (D) Models may reference other models on the same row through explicit references, or on a different row
            through explicit references.

    """
    #: Dictionary that can be expanded into unchanging keyword arguments
    # to create a host admin user with _create_fdp_user(...) and _create_fdp_user_without_assert(...).
    __create_host_admin_user_kwargs = {'is_host': True, 'is_administrator': True, 'is_superuser': False}

    #: Name of action field to submit via POST to start an import.
    __post_action_field = 'action'

    #: Name of file field to submit via POST to start an import.
    __post_field_field = 'file'

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
        self.__create_import_url = reverse('wholesale:create_import')

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
