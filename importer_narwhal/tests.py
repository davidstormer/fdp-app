from unittest import skip

import tablib

from functional_tests.common_import_export import import_record_with_extid
from .narwhal import BooleanWidgetValidated, resource_model_mapping
from core.models import PersonAlias
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4
from core.models import Person


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
                1,
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

    def test_external_id_keys(self):
        """Test that importer supports using external IDs to reference existing records in the system
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

        print(command_output.getvalue())
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


    @skip
    def natural_keys(self):
        pass

    @skip
    def generate_new_types(self):
        pass
