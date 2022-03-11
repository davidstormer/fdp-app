import tablib
from django.test import TestCase
from .narwhal import BooleanWidgetValidated, resource_model_mapping
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

from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4
from core.models import Person


class NarwhalImportCommand(TestCase):
    """Functional test
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
            