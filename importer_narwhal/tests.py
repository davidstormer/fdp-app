from datetime import datetime
import tablib
from django.core.exceptions import ValidationError
from django.db import models

from bulk.models import BulkImport
from functional_tests.common_import_export import import_record_with_extid
from sourcing.models import Content
from supporting.models import PersonIdentifierType, PersonRelationshipType
from .models import validate_import_sheet_extension, validate_import_sheet_file_size
from .narwhal import BooleanWidgetValidated, resource_model_mapping
from core.models import PersonAlias, PersonIdentifier, PersonRelationship
from django.test import TestCase, SimpleTestCase
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
        dataset = tablib.Dataset(['person quasicontinuous'], headers=['name'])
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
            csv_writer = csv.DictWriter(csv_fd, ['person', 'name'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['person'] = person_record.pk
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

    def test_external_id_keys_success_scenario(self):
        """Test that importer supports using external IDs to reference existing records in the system
        Uses PersonAlias records to test this
        """

        # Given theres an import sheet that references an existing record in the system (e.g. foreign key relationship)
        existing_record = import_record_with_extid(Person, {"name": 'gnathopod'}, external_id='carbocinchomeronic')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person__external', 'name'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external'] = existing_record['external_id']
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
            csv_writer = csv.DictWriter(csv_fd, ['person__external', 'name'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external'] = existing_record['external_id']
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
            csv_writer = csv.DictWriter(csv_fd, ['person__external', 'name'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external'] = existing_record['external_id']
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
            csv_writer = csv.DictWriter(csv_fd, ['person__external', 'identifier', 'person_identifier_type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external'] = existing_record['external_id']
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

    def test_generate_new_types_person_identifier_types(self):
        """Test that importer can add new "types" when they don't exist in the system yet
        Uses PersonIdentifier records to test this
        """
        # Given theres an import sheet that references a type that's NOT in the system
        existing_record = import_record_with_extid(Person, {"name": 'marteline'}, external_id='sinusoidal')
        # person_identifier_type = PersonIdentifierType.objects.create(name='unkissed')

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['person__external', 'identifier', 'person_identifier_type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['person__external'] = existing_record['external_id']
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
            csv_writer = csv.DictWriter(csv_fd, ['subject_person__external', 'object_person__external', 'type'])
            csv_writer.writeheader()
            for i in range(1):
                row = {}
                row['subject_person__external'] = person_subject['external_id']
                row['object_person__external'] = person_object['external_id']
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

    def test_update_existing_records(self):
        # Given there are existing records in the system
        existing_records = []
        for i in range(10):
            existing_records.append(Person.objects.create(name='Old Name'))
        # and Given there's an import sheet that references them by pk
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            csv_writer = csv.DictWriter(csv_fd, ['id', 'name'])
            csv_writer.writeheader()
            for existing_record in existing_records:
                row = {}
                row['id'] = existing_record.pk
                row['name'] = 'NEW Name'
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
                person_csv_writer = csv.DictWriter(person_csv_fd, ['external_id', 'name'])
                person_csv_writer.writeheader()
                for i in range(3):
                    row = {}
                    row['external_id'] = f'person-extid-{uuid4()}'
                    row['name'] = f"person-name-{uuid4()}"
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
                csv_writer = csv.DictWriter(csv_fd, ['name', 'person__external'])
                csv_writer.writeheader()
                for person in person_import_result['imported_records']:
                    row = {}
                    row['name'] = f"alias-name-{uuid4()}"
                    row['person__external'] = person['external_id']
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
        content_import_result = import_person_alias_records()

        # Then I should not see "Can't find external id" in the output of the alias import command
        self.assertNotIn(
            "Can't find external id",
            content_import_result['command_output']
        )
        # Then the content records should be linked to the person records
        import pdb; pdb.set_trace()
