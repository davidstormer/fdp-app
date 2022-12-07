from unittest.mock import patch
from datetime import datetime
import tablib
from bulk.models import BulkImport
from functional_tests.common_import_export import import_record_with_extid
from supporting.models import PersonIdentifierType, PersonRelationshipType
from .models import ImportBatch
from .narwhal import BooleanWidgetValidated, resource_model_mapping
from core.models import PersonAlias, PersonIdentifier, PersonRelationship
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4
from core.models import Person


class NarwhalDeleteImportBatch(TestCase):
    """Functional tests
    """

    def test_success_scenario(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN an import has been run
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
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # WHEN I run the delete_import_batch command on it and type in the batch number
            batch_number = ImportBatch.objects.last().pk
            with patch('builtins.input', lambda *args: batch_number):
                call_command('narwhal_delete_import_batch', batch_number, stdout=command_output)

            # THEN the records should be removed from the system
            self.assertEqual(
                0,
                Person.objects.all().count()
            )

    def test_update_existing_records(self):
        # Given an import was run that included updates
        existing_records = []
        for i in range(10):
            existing_records.append(Person.objects.create(name='Old Name'))
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            csv_writer = csv.DictWriter(csv_fd, ['id', 'name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for existing_record in existing_records:
                row = {}
                row['id'] = existing_record.pk
                row['name'] = 'NEW Name'
                csv_writer.writerow(row)
            csv_fd.flush()  # ... Make sure it's actually written to the filesystem!
            command_output = StringIO()
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

        # When I run the delete import batch command
        # WHEN I run the delete_import_batch command on it and type in the batch number
        batch_number = ImportBatch.objects.last().pk
        delete_import_batch_command_output_stream = StringIO()
        with patch('builtins.input', lambda *args: batch_number):
            call_command('narwhal_delete_import_batch', batch_number, stdout=delete_import_batch_command_output_stream)
        output = delete_import_batch_command_output_stream.getvalue()

        # And none of the records from the batch should be deleted
        for record in existing_records:
            self.assertEqual(
                "NEW Name",
                Person.objects.get(pk=record.pk).name
            )

        # Then it should give me an error
        self.assertIn(
            'Cannot delete',
            output
        )

    # TODO: handle missing records
    def test_delete_bulkimport_external_ids(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN an import has been run
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['external_id', 'name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(10):
                row = {}
                row['external_id'] = f'test_external_id-{i}'
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            # WHEN I run the delete_import_batch command on it and type in the batch number
            batch_number = ImportBatch.objects.last().pk
            with patch('builtins.input', lambda *args: batch_number):
                call_command('narwhal_delete_import_batch', batch_number, stdout=command_output)

            # THEN the records should be removed from the system
            self.assertEqual(
                0,
                BulkImport.objects.count()
            )
