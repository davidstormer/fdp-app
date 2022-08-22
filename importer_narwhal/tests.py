from datetime import datetime
from unittest import skip

import tablib
from django.core.exceptions import ValidationError
from django.db import models

from bulk.models import BulkImport
from functional_tests.common_import_export import import_record_with_extid
from sourcing.models import Content, ContentPerson, Attachment
from supporting.models import PersonIdentifierType, PersonRelationshipType, SituationRole, ContentType, TraitType, \
    Trait, Title, County, LeaveStatus, State, PersonGroupingType, GroupingRelationshipType, AttachmentType
from .models import validate_import_sheet_extension, validate_import_sheet_file_size
from .narwhal import BooleanWidgetValidated, resource_model_mapping, create_batch_from_disk, do_dry_run
from core.models import PersonAlias, PersonIdentifier, PersonRelationship, PersonTitle, PersonPayment, Grouping, \
    PersonGrouping, GroupingAlias, GroupingRelationship
from django.test import TestCase, SimpleTestCase, tag
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4
from core.models import Person


class NarwhalSimpleTestCase(SimpleTestCase):
    def test_validate_import_sheet_extension(self):
        with self.subTest(msg="success"):
            validate_import_sheet_extension('hello.csv')

        with self.subTest(msg="wrong extension"):
            with self.assertRaises(ValidationError):
                validate_import_sheet_extension('hello.ppt')

        with self.subTest(msg="missing extension"):
            with self.assertRaises(ValidationError):
                validate_import_sheet_extension('hello')

    def test_validate_import_sheet_file_size(self):
        with self.subTest(msg='too big'):
            file = models.FileField()  # Does this really make a FileField instance?
            file.size = 1000000 * 11
            with self.assertRaises(ValidationError):
                validate_import_sheet_file_size(file)

        with self.subTest(msg='not too big'):
            file = models.FileField()
            file.size = 1000000 * 9
            validate_import_sheet_file_size(file)


class NarwhalTestCase(TestCase):

    def test_booleanwidgetvalidated(self):
        with self.subTest(value='INVALID'):
            with self.assertRaises(ValueError):
                BooleanWidgetValidated().clean(value='INVALID')
        with self.subTest(value='CHECKED'):
            self.assertTrue(
                BooleanWidgetValidated().clean(value='TRUE'),
                msg='Unexpected validation error for "TRUE"'
            )
        with self.subTest(value='FALSE'):
            self.assertFalse(
                BooleanWidgetValidated().clean(value='FALSE'),
                msg='Unexpected validation error for "FALSE"'
            )
        with self.subTest(value=''):
            self.assertIsNone(
                BooleanWidgetValidated().clean(value=''),
                msg='Unexpected validation error for blank value'
            )

    def test_resources(self):
        ResourceClass = resource_model_mapping['Person']
        resource = ResourceClass()
        dataset = tablib.Dataset(['person quasicontinuous', 'TRUE'], headers=['name', 'is_law_enforcement'])
        result = resource.import_data(dataset, dry_run=False)
        self.assertEqual(
            1,
            Person.objects.all().count()
        )
        self.assertEqual(Person.objects.last().name,
            'person quasicontinuous'
        )


class NarwhalImportCommand(TestCase):
    """Functional tests
    """

    def test_success_scenario(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is a csv describing a new Person record
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the command with the target model and CSV file as positional arguments
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # THEN the records should be added to the system
            for row in imported_records:
                self.assertEqual(
                    True,
                    Person.objects.get(name=row['name']).is_law_enforcement,
                )
            self.assertEqual(
                10,
                Person.objects.all().count()
            )

    def test_validation_error_scenario(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is a csv with an invalid value
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                imported_records.append(row)

            imported_records[7]['is_law_enforcement'] = 'INVALID VALUE'  # <- invalid boolean

            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the command with the target model and CSV file as positional arguments
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # THEN the records should not be added to the system
            self.assertEqual(
                0,
                Person.objects.all().count()
            )
            # THEN I should see an error in the output
            self.assertIn(
                'is_law_enforcement',
                command_output.getvalue()
            )
            self.assertIn(
                'Enter a valid boolean value',
                command_output.getvalue()
            )

            # AND WHEN I run the import_history command
            history_command_output = StringIO()
            time_started = datetime.now()
            call_command('narwhal_import_history', stdout=history_command_output)

            # THEN the listing should indiciate "Errors encountered"
            self.assertIn(
                "Errors encountered",
                history_command_output.getvalue()
            )

    def test_exception_error_scenario(self):
        """Handle database layer errors
        """

        # Given there's an import sheet that tries to create a Person identifier that already exists
        # And there are several rows before the problem row
        command_output = StringIO()

        person_record = Person.objects.create(name='My Test Person')
        PersonAlias.objects.create(person=person_record, name='Joe')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person', 'name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['person'] = person_record.pk
                row['is_law_enforcement'] = 'checked'
                row['name'] = f"alias-{uuid4()}"
                imported_records.append(row)
            imported_records[7]['name'] = 'Joe'  # <- Dupe

            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            call_command('narwhal_import', 'PersonAlias', csv_fd.name, stdout=command_output)

            # THEN none of the records from the sheet should be added to the system
            self.assertEqual(
                1,  # <-- 1 for the existing record
                PersonAlias.objects.all().count()
            )
            # THEN I should see an error in the output
            self.assertIn(
                '8 | duplicate key value violates unique constraint',
                command_output.getvalue()
            )
            self.assertIn(
                'Joe',
                command_output.getvalue()
            )
            # But not more than once
            self.assertEqual(
                1,
                command_output.getvalue().count('violates unique constraint')
            )

            # AND WHEN I run the import_history command
            history_command_output = StringIO()
            time_started = datetime.now()
            call_command('narwhal_import_history', stdout=history_command_output)

            # THEN the listing should indiciate "Errors encountered"
            self.assertIn(
                "Errors encountered",
                history_command_output.getvalue()
            )

    def test_exception_error_scenario_multiple(self):
        """Handle database layer errors
        """

        # Given there's an import sheet that tries to create a Person identifier that already exists
        # And there are several rows before the problem row
        command_output = StringIO()

        person_record = Person.objects.create(name='My Test Person')
        PersonAlias.objects.create(person=person_record, name='toxiphoric')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person', 'name'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['person'] = person_record.pk
                row['name'] = f"alias-{uuid4()}"
                imported_records.append(row)
            imported_records[3]['name'] = 'toxiphoric'  # <- Dupe #1
            imported_records[7]['name'] = 'toxiphoric'  # <- Dupe #2

            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            call_command('narwhal_import', 'PersonAlias', csv_fd.name, stdout=command_output)

            # THEN I should see an error in the output for each instance of the exception
            self.assertIn(
                '4 | duplicate key value violates unique constraint',
                command_output.getvalue()
            )
            self.assertIn(
                '8 | duplicate key value violates unique constraint',
                command_output.getvalue()
            )
            self.assertEqual(
                2,
                command_output.getvalue().count('violates unique constraint')
            )

    def test_create_external_ids(self):
        # Given there is an import sheet with an "external_id" column,
        # which specifies that a new external id should be created when the record is imported.
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_rows = []
            csv_writer = csv.DictWriter(csv_fd, ['external_id', 'name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(3):
                row = {}
                row['external_id'] = f'external-id-{uuid4()}'
                row['is_law_enforcement'] = 'checked'
                row['name'] = f'Test Person {uuid4()}'
                csv_writer.writerow(row)
                imported_rows.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # When I run the import
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # Then I should see new BulkImport records in the system linking the external ids to the records
            try:
                for imported_row in imported_rows:
                    BulkImport.objects.get(pk_imported_from=imported_row['external_id'])
            except BulkImport.DoesNotExist:
                self.fail(f"Couldn't find external id {imported_row['external_id']}")

    def test_duplicate_external_id_with_existing(self):
        # Given there is an import sheet with an external_id that already exists in the system
        duplicate_external_id = f'external-id-{uuid4()}'

        BulkImport.objects.create(
            table_imported_to=Person.get_db_table(),
            pk_imported_to=1,
            pk_imported_from=duplicate_external_id,
            data_imported='{}'  # make constraints happy...
        )

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_rows = []
            csv_writer = csv.DictWriter(csv_fd, ['external_id', 'name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(3):
                row = {}
                row['external_id'] = f'external-id-{uuid4()}'
                row['is_law_enforcement'] = 'checked'
                row['name'] = f'Test Person {uuid4()}'
                csv_writer.writerow(row)
                imported_rows.append(row)
            row = {}
            row['external_id'] = duplicate_external_id  # <-- this
            row['is_law_enforcement'] = 'checked'
            row['name'] = f'Test Person {uuid4()}'
            csv_writer.writerow(row)
            imported_rows.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # When I run the import
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # Then none of the records should have been imported
            self.assertEqual(
                0,
                Person.objects.all().count(),
                msg="Records were imported"
            )
            # Then I should see an error
            self.assertIn(
                'External ID already exists',
                command_output.getvalue()
            )

    def test_duplicate_external_id_within_sheet(self):
        # Given there is an import sheet with duplicate external_id
        # (not that already exist in the system)
        duplicate_external_id = f'external-id-{uuid4()}'

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_rows = []
            csv_writer = csv.DictWriter(csv_fd, ['external_id', 'name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(3):
                row = {}
                row['external_id'] = f'external-id-{uuid4()}'
                row['is_law_enforcement'] = 'checked'
                row['name'] = f'Test Person {uuid4()}'
                csv_writer.writerow(row)
                imported_rows.append(row)
            for i in range(2):                                # <-- this
                row = {}
                row['external_id'] = duplicate_external_id
                row['is_law_enforcement'] = 'checked'
                row['name'] = f'Test Person {uuid4()}'
                csv_writer.writerow(row)
                imported_rows.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # When I run the import
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # Then none of the records should have been imported
            self.assertEqual(
                0,
                Person.objects.all().count(),
                msg="Records were imported"
            )
            # Then I should see an error
            self.assertIn(
                'External ID already exists',
                command_output.getvalue()
            )

    def test_external_id_keys_success_scenario(self):
        """Test that importer supports using external IDs to reference existing records in the system
        Uses PersonAlias records to test this
        """

        # Given theres an import sheet that references an existing record in the system (e.g. foreign key relationship)
        existing_record = import_record_with_extid(Person, {"name": 'gnathopod'}, external_id='carbocinchomeronic')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person__external_id', 'name'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external_id'] = existing_record['external_id']
                row['name'] = f"alias-{uuid4()}"
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonAlias', csv_fd.name, stdout=command_output)

        # Then I shouldn't see an error message
        self.assertNotIn(
            'violates not-null constraint',
            command_output.getvalue()
        )
        # Then I should see the new record linked to the existing one
        self.assertEqual(
            existing_record['record'].pk,
            PersonAlias.objects.first().person.pk
        )

    def test_external_id_keys_missing_external_id_scenario(self):
        """Test that a missing person identifier is gracefully handled
        """

        # Given theres an import sheet that references an existing record in the system (e.g. foreign key relationship)
        # BUT the external id is missing...
        existing_record = import_record_with_extid(Person, {"name": 'gnathopod'}, external_id='carbocinchomeronic')

        BulkImport.objects.last().delete()  # <--- this

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person__external_id', 'name'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external_id'] = existing_record['external_id']
                row['name'] = f"alias-{uuid4()}"
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonAlias', csv_fd.name, stdout=command_output)

        # Then I should see an error message
        self.assertIn(
            "Can't find external id carbocinchomeronic",
            command_output.getvalue()
        )
        # Then the records from the sheet shouldn't be imported
        self.assertEqual(
            0,
            PersonAlias.objects.all().count()
        )

    def test_external_id_keys_missing_record_scenario(self):
        """Test that a missing record is gracefully handled when referenced by an external id
        """

        # Given theres an import sheet that references an existing record in the system (e.g. foreign key relationship)
        # BUT the external id is missing...
        existing_record = import_record_with_extid(Person, {"name": 'gnathopod'}, external_id='carbocinchomeronic')

        Person.objects.last().delete()  # <--- this

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person__external_id', 'name'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external_id'] = existing_record['external_id']
                row['name'] = f"alias-{uuid4()}"
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonAlias', csv_fd.name, stdout=command_output)

        # Then I should see an error message
        self.assertIn(
            "Can't find record, does not exist!",
            command_output.getvalue()
        )
        # Then the records from the sheet shouldn't be imported
        self.assertEqual(
            0,
            PersonAlias.objects.all().count()
        )

    def test_natural_keys_person_identifier_type(self):
        """Test that the importer can find person_identifier_type by its value, rather than pk
        """
        # Given theres an import sheet that references an existing record in the system by name value, not identifier
        existing_record = import_record_with_extid(Person, {"name": 'marteline'}, external_id='sinusoidal')
        person_identifier_type = PersonIdentifierType.objects.create(name='unkissed')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person__external_id', 'identifier', 'person_identifier_type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external_id'] = existing_record['external_id']
                row['identifier'] = f"identifier-{uuid4()}"
                row['person_identifier_type'] = 'unkissed'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonIdentifier', csv_fd.name, stdout=command_output)

        # Then I should see the new record linked to the existing one
        self.assertEqual(
            existing_record['record'].pk,
            PersonIdentifier.objects.first().person.pk
        )

    def test_external_ids_on_natural_key_field(self):
        # Given there's an import sheet with an '__external_id' field on a natural key lookup field (e.g.
        # person_identifier_type)
        person_identifier_type_import = \
            import_record_with_extid(PersonIdentifierType, {"name": 'person-identifier-type-marteline'},
                                     external_id='external-id-sinusoidal')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person', 'identifier', 'person_identifier_type__external_id'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person_identifier_type__external_id'] = 'external-id-sinusoidal'
                row['identifier'] = f"identifier-{uuid4()}"
                row['person'] = Person.objects.create(name=f"person-{uuid4()}").pk
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the import
            command_output = StringIO()
            call_command('narwhal_import', 'PersonIdentifier', csv_fd.name, stdout=command_output)

        # Then I should see the new record linked to the existing record referenced by external id
        self.assertEqual(
            PersonIdentifier.objects.last().person_identifier_type,
            person_identifier_type_import['record']
        )

    def test_external_ids_on_natural_key_field_counties(self):
        # Given there's an import sheet with an '__external_id' field on a natural key lookup field (e.g.
        # person_identifier_type)
        county_import = import_record_with_extid(
            County,
            {
                "name": 'person-identifier-type-marteline',
                "state": State.objects.create(name='Washington')
            },
            external_id='external-id-sinusoidal'
        )

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'counties__external_id', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['counties__external_id'] = 'external-id-sinusoidal'
                row['name'] = f"name-{uuid4()}"
                row['is_law_enforcement'] = 'checked'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the import
            command_output = StringIO()
            call_command('narwhal_import', 'Grouping', csv_fd.name, stdout=command_output)

        # Then I should see the new record linked to the existing record referenced by external id
        self.assertNotIn(
            'County matching query does not exist',
            command_output.getvalue()
        )
        self.assertNotIn(
            "Direct assignment to the forward side of a many-to-many set is prohibited",
            command_output.getvalue()
        )
        self.assertEqual(
            Grouping.objects.last().counties.all()[0],
            county_import['record']
        )


    def test_generate_new_types_person_identifier_types(self):
        """Test that importer can add new "types" when they don't exist in the system yet
        Uses PersonIdentifier records to test this
        """
        # Given theres an import sheet that references a type that's NOT in the system
        existing_record = import_record_with_extid(Person, {"name": 'marteline'}, external_id='sinusoidal')
        # person_identifier_type = PersonIdentifierType.objects.create(name='unkissed')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person__external_id', 'identifier', 'person_identifier_type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external_id'] = existing_record['external_id']
                row['identifier'] = f"identifier-{uuid4()}"
                row['person_identifier_type'] = 'unkissed'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonIdentifier', csv_fd.name, stdout=command_output)

        # Then I should see the new record linked to the existing one
        self.assertEqual(
            existing_record['record'].pk,
            PersonIdentifier.objects.first().person.pk
        )

    def test_generate_new_types_person_relationship_types(self):
        """Test that importer can add new "types" when they don't exist in the system yet
        Uses PersonRelationship records to test this
        """
        # Given there's an import sheet that references a type that's NOT in the system
        person_subject = import_record_with_extid(Person, {"name": 'marteline'}, external_id='sinusoidal')
        person_object = import_record_with_extid(Person, {"name": 'marteline2'}, external_id='sinusoidal2')
        # person_relationship_type = PersonRelationshipType.objects.create(name='commonsensical')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['subject_person__external_id', 'object_person__external_id', 'type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['subject_person__external_id'] = person_subject['external_id']
                row['object_person__external_id'] = person_object['external_id']
                row['type'] = 'vaudeville'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonRelationship', csv_fd.name, stdout=command_output)

        # Then I should see the new type created
        self.assertEqual(
            'vaudeville',
            PersonRelationshipType.objects.last().name
        )

        # And the person relationship should use the new type
        self.assertEqual(
            'vaudeville',
            PersonRelationship.objects.last().type.name
        )

    def test_generate_new_types_content_types(self):
        """Test that importer can add new "types" when they don't exist in the system yet
        Uses Content records to test this
        """
        # Given theres an import sheet that references a type that's NOT in the system
        # NOT IN THE SYSTEM: content_type = ContentType.objects.create(name='restopper')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['description', 'type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['description'] = f"description-{uuid4()}"
                row['type'] = 'restopper'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'Content', csv_fd.name, stdout=command_output)

        # Then I should see a new content type created matching the name 'restopper'
        self.assertEqual(
            1,
            ContentType.objects.all().count(),
            msg="New content type wasn't created"
        )
        self.assertEqual(
            'restopper',
            Content.objects.first().type.name
        )

    def test_generate_new_types_person_content_situation_role(self):
        """Test that importer can add new "types" when they don't exist in the system yet
        Uses ContentPerson situation role
        """
        # Given theres a ContentPerson import sheet that references a situation role that's NOT in the system
        # NOT IN THE SYSTEM: situation_role = SituationRole.objects.create(name='unfrequentedness')
        content = Content.objects.create(description='Test Content')
        person = Person.objects.create(name='Test Person')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['content', 'person', 'situation_role'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['content'] = content.pk
                row['person'] = person.pk
                row['situation_role'] = 'unfrequentedness'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'ContentPerson', csv_fd.name, stdout=command_output)

        # Then I should see a new SituationRole created matching the name 'unfrequentedness'
        self.assertEqual(
            1,
            SituationRole.objects.all().count(),
            msg="New SituationRole wasn't created"
        )
        self.assertEqual(
            'unfrequentedness',
            ContentPerson.objects.first().situation_role.name
        )

    def test_generate_new_types_person_title_title(self):
        """Test that importer can add new "types" when they don't exist in the system yet
        Uses PersonTitle Title
        """
        # Given theres a PersonTitle import sheet that references a Title that's NOT in the system
        # NOT IN THE SYSTEM: situation_role = Title.objects.create(name='windling')
        person = Person.objects.create(name='Test Person')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person', 'title'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person'] = person.pk
                row['title'] = 'windling'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonTitle', csv_fd.name, stdout=command_output)

        # Then I should see a new SituationRole created matching the name 'windling'
        self.assertEqual(
            1,
            Title.objects.all().count(),
            msg="New Title wasn't created"
        )
        self.assertEqual(
            'windling',
            PersonTitle.objects.first().title.name
        )

    def test_generate_new_person_aliases_for_new_person(self):
        # Given there's a Person import sheet that has Aliases as comma separated values in it
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is a csv describing a new Person record
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'person_aliases', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                row['person_aliases'] = 'rallier, medisect'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the command with the target model and CSV file as positional arguments
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

        # Then I should see the new PersonAliases created, and linked to the new Person record
        self.assertEqual(
            2,
            PersonAlias.objects.count()
        )

    def test_update_person_aliases_for_existing_person_no_other_changes(self):
        # Given there's an import sheet that updates aliases (and only aliases) for an existing Person record
        person_record = Person.objects.create(name='test person')
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['id', 'name', 'person_aliases', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['id'] = person_record.pk
                row['name'] = f'test person'  # <- Same value
                row['person_aliases'] = 'rallier, NEW ALIAS misconstructive, medisect'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the command with the target model and CSV file as positional arguments
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

        # Then I should see a new PersonAliase created, and linked to the new Person record
        self.assertEqual(
            3,
            PersonAlias.objects.count()
        )

    def test_update_person_aliases_for_existing_person_with_other_changes(self):
        # Given there's an import sheet that updates aliases _and_ name for an existing Person record
        person_record = Person.objects.create(name='test person')
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['id', 'name', 'person_aliases', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['id'] = person_record.pk
                row['name'] = f'test person UPDATED'  # <- Different value
                row['person_aliases'] = 'rallier, NEW ALIAS misconstructive, medisect'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the command with the target model and CSV file as positional arguments
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

        # Then I should see a new PersonAliase created, and linked to the new Person record
        self.assertEqual(
            3,
            PersonAlias.objects.count()
        )

    def test_generate_new_grouping_aliases_for_new_grouping(self):
        # Given there's a Grouping import sheet that has Aliases as comma separated values in it
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is a csv describing a new Grouping record
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'grouping_aliases', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['name'] = f'Test Grouping {uuid4()}'
                row['grouping_aliases'] = 'readmittance, journeycake'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the grouping with the target model and CSV file as positional arguments
            command_output = StringIO()
            call_command('narwhal_import', 'Grouping', csv_fd.name, stdout=command_output)

        # Then I should see the new GroupingAlias created, and linked to the new Person record
        self.assertEqual(
            2,
            GroupingAlias.objects.count()
        )

    def test_grouping_sheet_add_relationships(self):
        # Given there's a grouping import sheet with relationships in a field patterned "grouping_relationship__[NAME]"
        # where [NAME] is a case insensitive string with hyphens instead of spaces. E.g. "grouping_relationship__reports-to"
        # and where [NAME] is an existing relationship type.
        # and where the related grouping already exists
        relationship_type = GroupingRelationshipType.objects.create(name="Exists in")
        existing_grouping1 = Grouping.objects.create(name="indulgentially")
        existing_grouping2 = Grouping.objects.create(name="indulgentially 2")

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'grouping_relationships__exists-in', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['name'] = 'New Command'
                row['grouping_relationships__exists-in'] = f"{existing_grouping1.pk},{existing_grouping2.pk}"
                row['is_law_enforcement'] = 'checked'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'Grouping', csv_fd.name, stdout=command_output)

        # Then I should see new GroupingRelationships with type "Reports to" linking the existing grouping and the
        # newly imported one
        self.assertEqual(
            2,
            GroupingRelationship.objects.count()
        )
        self.assertEqual(
            relationship_type,
            GroupingRelationship.objects.first().type
        )
        self.assertEqual(
            relationship_type,
            GroupingRelationship.objects.last().type
        )
        self.assertEqual(
            existing_grouping1,
            GroupingRelationship.objects.first().object_grouping
        )
        self.assertEqual(
            existing_grouping2,
            GroupingRelationship.objects.last().object_grouping
        )

    def test_validation_step_column_mapping_regex_patterns(self):
        """Test that regex based column names are recognized when doing dry run checks"""
        # Given there is a batch with an import sheet with a column named grouping_relationships__reports-to
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['count', 'grouping_relationships__exists-in', 'control'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['count'] = 'should be "counties" so should raise a warning'
                row['grouping_relationships__exists-in'] = f"hello world"
                row['control'] = 'control should always raise a warning'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!
            import_batch = create_batch_from_disk('Grouping', csv_fd.name)
        # When I do a dry run
        do_dry_run(import_batch)
        # Then I should not see a warning about the column not being recognized
        self.assertNotIn(
            'grouping_relationships__exists-in',
            import_batch.general_errors
        )
        with self.subTest(msg="'count' doesn't match 'counties'"):
            self.assertIn(
                "ERROR: 'count' not a valid column name for Grouping imports",
                import_batch.general_errors
            )
        with self.subTest(msg="'control' should always raise a warning"):
            self.assertIn(
                "ERROR: 'control' not a valid column name for Grouping imports",
                import_batch.general_errors
            )

    def test_column_name_validation_external_id_columns(self):
        """Test that simple foreign key column names with __external_id are recognized when doing dry run checks"""
        # Given there's an import sheet containing the '__external_id' column
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['state__external_id'])
            csv_writer.writeheader()
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # When I do a dry run
            batch_record = create_batch_from_disk('County', csv_fd.name)
            do_dry_run(batch_record)

            # Then I should see no errors in the batch
            self.assertFalse(
                batch_record.general_errors
            )
            self.assertFalse(
                batch_record.errors_encountered
            )

    def test_grouping_sheet_add_relationships_by_external_id(self):
        # Given there's a grouping import sheet with relationships in a field patterned
        # "grouping_relationship__external_id__[NAME]"
        # where [NAME] is a case insensitive string with hyphens instead of spaces. E.g.
        # "grouping_relationship__external_id__reports-to"
        # and where [NAME] is an existing relationship type.
        # and where the related grouping already exists
        relationship_type = GroupingRelationshipType.objects.create(name="Exists in")
        existing_grouping_1_external_id = \
            import_record_with_extid(Grouping, {"name": 'indulgentially1'}, external_id='postembryonic1')
        existing_grouping_2_external_id = \
            import_record_with_extid(Grouping, {"name": 'indulgentially2'}, external_id='postembryonic2')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'grouping_relationships__external_id__exists-in',
                                                 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['name'] = 'New Command'
                row['grouping_relationships__external_id__exists-in'] = \
                    f"{existing_grouping_1_external_id['external_id']},{existing_grouping_2_external_id['external_id']}"
                row['is_law_enforcement'] = 'checked'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'Grouping', csv_fd.name, stdout=command_output)

        # Then I should see a new GroupingRelationship with type "Reports to" linking the existing grouping and the
        # newly imported one
        self.assertEqual(
            2,
            GroupingRelationship.objects.count()
        )
        self.assertEqual(
            relationship_type,
            GroupingRelationship.objects.first().type
        )
        self.assertEqual(
            relationship_type,
            GroupingRelationship.objects.last().type
        )
        self.assertEqual(
            existing_grouping_1_external_id['record'],
            GroupingRelationship.objects.first().object_grouping
        )
        self.assertEqual(
            existing_grouping_2_external_id['record'],
            GroupingRelationship.objects.last().object_grouping
        )

    def test_grouping_sheet_add_relationships_by_external_id_ignore_blank_cells(self):
        # Given there's a grouping import sheet with relationships in a field patterned
        # "grouping_relationship__external_id__[NAME]"
        # where [NAME] is a case insensitive string with hyphens instead of spaces. E.g.
        # "grouping_relationship__external_id__reports-to"
        # and where [NAME] is an existing relationship type.
        # and where the related grouping already exists
        GroupingRelationshipType.objects.create(name="Exists in")
        existing_grouping_external_id = \
            import_record_with_extid(Grouping, {"name": 'indulgentially'}, external_id='postembryonic')['external_id']

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'grouping_relationships__external_id__exists-in',
                                                 'is_law_enforcement'])
            csv_writer.writeheader()
            row = {}
            row['name'] = 'New Command 1'
            row['grouping_relationships__external_id__exists-in'] = ''  # <- THIS
            row['is_law_enforcement'] = 'checked'
            imported_records.append(row)
            row = {}
            row['name'] = 'New Command 2'
            row['grouping_relationships__external_id__exists-in'] = existing_grouping_external_id
            row['is_law_enforcement'] = 'checked'
            imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'Grouping', csv_fd.name, stdout=command_output)

        # Then I shouldn't see an error message
        self.assertNotIn(
            "BulkImport matching query does not exist",
            command_output.getvalue()
        )
        # Then I should see a new GroupingRelationship with type "Reports to" linking the existing grouping and the
        # newly imported one
        self.assertEqual(
            1,
            GroupingRelationship.objects.count()
        )

    def test_grouping_belongs_to_grouping_with_external_id(self):
        # Given there's an import sheet with a column named `belongs_to_grouping__external` that references an
        # exiting grouping by external id.
        existing_grouping_external_id = \
            import_record_with_extid(Grouping, {"name": 'Existing Command'}, external_id='postembryonic')['external_id']

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'belongs_to_grouping__external_id', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['name'] = 'New Command'
                row['belongs_to_grouping__external_id'] = existing_grouping_external_id
                row['is_law_enforcement'] = 'checked'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # When I do an import
            command_output = StringIO()
            call_command('narwhal_import', 'Grouping', csv_fd.name, stdout=command_output)

        # Then the newly added grouping's belongs_to_grouping field should point to the existing record
        self.assertEqual(
            Grouping.objects.last().belongs_to_grouping,
            Grouping.objects.first()
        )

    def test_generate_new_types_person_grouping_type(self):
        """Test that importer can add new "types" when they don't exist in the system yet
        Uses PersonGrouping Type
        """
        # Given theres a PersonGrouping import sheet that references a PersonGroupingType that's NOT in the system
        # NOT IN THE SYSTEM: grouping_type = PersonGroupingType.objects.create(name='ethaldehyde')
        person = Person.objects.create(name='Test Person')
        group = Grouping.objects.create(name='Test Group')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person', 'grouping', 'type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person'] = person.pk
                row['grouping'] = group.pk
                row['type'] = 'ethaldehyde'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonGrouping', csv_fd.name, stdout=command_output)

        # Then I should see a new PersonGroupingType created matching the name 'ethaldehyde'
        self.assertEqual(
            1,
            PersonGroupingType.objects.all().count(),
            msg="New PersonGroupingType wasn't created"
        )
        self.assertEqual(
            'ethaldehyde',
            PersonGrouping.objects.first().type.name
        )

    def test_person_payment_handle_county_leave_status(self):
        """Test that PersonPayment
        county is 'natural key' but is not 'get or create' -- because it requires a 'state' value which can't be assumed
        leave_status is regular 'get or create'
        """
        # Given theres a PersonPayment import sheet that references a leave status that's NOT in the system
        # and a county that IS in the system.
        # NOT IN THE SYSTEM: leave_status = LeaveStatus.objects.create(name='shareman')
        state = State.objects.create(name='Washington')
        county = County.objects.create(name='nocuous', state=state)
        person = Person.objects.create(name='Test Person')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person', 'county', 'leave_status'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person'] = person.pk
                row['county'] = 'nocuous'
                row['leave_status'] = 'shareman'
                imported_records.append(row)
            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # WHEN I run the command on the sheet
            command_output = StringIO()
            call_command('narwhal_import', 'PersonPayment', csv_fd.name, stdout=command_output)

        # Then I should see a new PersonPayment created
        self.assertEqual(
            'nocuous',
            PersonPayment.objects.first().county.name
        )
        self.assertEqual(
            'shareman',
            PersonPayment.objects.first().leave_status.name
        )
        # and a new leave status
        self.assertEqual(
            1,
            LeaveStatus.objects.all().count(),
            msg="New LeaveStatus wasn't created"
        )
        # and no new county
        self.assertEqual(
            1,
            County.objects.all().count(),
            msg="New County wasn't created"
        )

    def test_update_existing_records(self):
        # Given there are existing records in the system
        existing_records = []
        for i in range(10):
            existing_records.append(Person.objects.create(name='Old Name'))
        # and Given there's an import sheet that references them by pk
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            csv_writer = csv.DictWriter(csv_fd, ['id', 'name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for existing_record in existing_records:
                row = {}
                row['id'] = existing_record.pk
                row['name'] = 'NEW Name'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # When I run the command
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # Then the records should be updated with the new values
            for record in Person.objects.all():
                self.assertEqual(
                    'NEW Name',
                    record.name
                )

            # Then there should be a message about them being updated
            self.assertIn(
                'update',
                command_output.getvalue()
            )

    def test_multiple_sheets_external_ids_person_personalias(self):
        """Test typical import scenario Person, Content, Incident
        """
        # Make person records
        # Given there's an import sheet of Person records with external ids of the new records and I import it
        def import_person_records() -> dict:
            with tempfile.NamedTemporaryFile(mode='w') as person_csv_fd:
                imported_person_records = []
                person_csv_writer = csv.DictWriter(person_csv_fd, ['external_id', 'name', 'is_law_enforcement'])
                person_csv_writer.writeheader()
                for i in range(3):
                    row = {}
                    row['external_id'] = f'person-extid-{uuid4()}'
                    row['name'] = f"person-name-{uuid4()}"
                    row['is_law_enforcement'] = 'checked'
                    imported_person_records.append(row)

                for row in imported_person_records:
                    person_csv_writer.writerow(row)
                person_csv_fd.flush()  # ... Make sure it's actually written to the filesystem!
                command_output = StringIO()
                call_command('narwhal_import', 'Person', person_csv_fd.name, stdout=command_output)
                return {
                    'imported_records': imported_person_records,
                    'command_output': command_output.getvalue()
                }
        person_import_result = import_person_records()

        # When I import person aliases linked to the person records by their newly created external ids
        def import_person_alias_records() -> dict:
            with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
                imported_records = []
                csv_writer = csv.DictWriter(csv_fd, ['name', 'person__external_id'])
                csv_writer.writeheader()
                for person in person_import_result['imported_records']:
                    row = {}
                    row['name'] = f"alias-name-{uuid4()}"
                    row['person__external_id'] = person['external_id']
                    imported_records.append(row)

                for row in imported_records:
                    csv_writer.writerow(row)
                csv_fd.flush()  # ... Make sure it's actually written to the filesystem!
                command_output = StringIO()
                call_command('narwhal_import', 'PersonAlias', csv_fd.name, stdout=command_output)
                return {
                    'imported_records': imported_records,
                    'command_output': command_output.getvalue()
                }
        person_alias_import_result = import_person_alias_records()

        # Then I should not see "Can't find external id" in the output of the alias import command
        self.assertNotIn(
            "Can't find external id",
            person_alias_import_result['command_output']
        )
        # Then the alias records should be linked to the person records
        for i in range(3):
            alias_name = person_alias_import_result['imported_records'][i]['name']
            person_alias = PersonAlias.objects.get(name=alias_name)
            self.assertEqual(
                person_import_result['imported_records'][i]['name'],
                person_alias.person.name
            )

    def test_m2m_attachment_content_relationships_by_pk(self):
        # Given there's an Content import sheet with a row pointing to an existing Attachment record
        attachment_record = Attachment.objects.create(
            name='Existing Attachment',
            type=AttachmentType.objects.create(name='Test Attachment Type')
        )

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'attachments'])
            csv_writer.writeheader()
            row = {}
            row['name'] = f"Test Content"
            row['attachments'] = attachment_record.pk
            imported_records.append(row)

            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # When I run the import
            command_output = StringIO()
            call_command('narwhal_import', 'Content', csv_fd.name, stdout=command_output)

            # Then I should see the new attachment and it should be connected to the existing Content record
            self.assertEqual(
                Attachment.objects.first(),
                Content.objects.last().attachments.last()
            )

    def test_m2m_attachment_content_relationships_by_external_id(self):
        # Given there's an Content import sheet with a row pointing to an existing Attachment record

        attachment_record = import_record_with_extid(
            Attachment,
            {
                "name": 'Existing Attachment',
                "type": AttachmentType.objects.create(name='Test Attachment Type')
            },
            external_id='overprocrastination'
        )

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'attachments__external_id'])
            csv_writer.writeheader()
            row = {}
            row['name'] = f"Test Content"
            row['attachments__external_id'] = attachment_record['external_id']
            imported_records.append(row)

            for row in imported_records:
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!

            # When I run the import
            command_output = StringIO()
            call_command('narwhal_import', 'Content', csv_fd.name, stdout=command_output)

            # Then I should see the new attachment and it should be connected to the existing Content record
            self.assertEqual(
                Attachment.objects.first(),
                Content.objects.last().attachments.last()
            )

    def test_m2m_directionality(self):
        """Test which fields show up on which model for m2m relationships
        """

        from import_export import resources

        with self.subTest(msg='From Attachment sheet'):
            from sourcing.models import Attachment

            class AttachmentResource(resources.ModelResource):
                class Meta:
                    model = Attachment

            self.assertNotIn(
                'contents',
                AttachmentResource().fields.keys()
            )

        with self.subTest(msg='From Content sheet'):
            from sourcing.models import Content

            class ContentResource(resources.ModelResource):
                class Meta:
                    model = Content

            self.assertIn(
                'attachments',
                ContentResource().fields.keys()
            )

    def test_person_require_is_law_enforcement(self):
        # Given there's a Person import sheet with no is_law_enforcement column
        # TODO: column exists, but cell is blank
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # When I do an import
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # Then no records should be imported
            self.assertEqual(
                0,
                Person.objects.all().count()
            )
            # Then I should get an error
            self.assertIn(
                '"is_law_enforcement" is missing but required',
                command_output.getvalue()
            )

    def test_grouping_require_is_law_enforcement(self):
        # Given there's a Person import sheet with no is_law_enforcement column
        # TODO: column exists, but cell is blank
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['name'] = f'Test Grouping {uuid4()}'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # When I do an import
            command_output = StringIO()
            call_command('narwhal_import', 'Grouping', csv_fd.name, stdout=command_output)

            # Then I should get an error
            self.assertIn(
                '"is_law_enforcement" is missing but required',
                command_output.getvalue()
            )
            # And no records should be imported
            self.assertEqual(
                0,
                Grouping.objects.all().count()
            )
