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

    # TODO: refuse when there's an update in the batch history
    # TODO: handle missing records
