import os
from datetime import datetime
from .models import ImportBatch
from .narwhal import do_import_from_disk
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4


class TestImportHistoryCommand(TestCase):
    def test_import_history_success_scenario(self):
        # GIVEN an import has been run
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(42):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            do_import_from_disk('Person', csv_fd.name)

            # WHEN I run the import_history command
            command_output = StringIO()
            time_started = datetime.now()
            call_command('narwhal_import_history', stdout=command_output)

            # THEN I should see a listing showing the number, import time, filename, model, number of records,
            # and whether it succeeded or not.
            output = command_output.getvalue()
            self.assertIn('Person', output)
            self.assertIn('42', output)
            self.assertIn(os.path.basename(csv_fd.name), output)

    def test_import_history_success_scenario_multiple(self):
        # GIVEN several imports have been run
        for x in range(3):
            with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
                imported_records = []
                csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
                csv_writer.writeheader()
                for i in range(31 + x):
                    row = {}
                    row['name'] = f'Test Person {uuid4()}'
                    row['is_law_enforcement'] = 'checked'
                    csv_writer.writerow(row)
                    imported_records.append(row)
                csv_fd.flush()  # Make sure it's actually written to the filesystem!
                do_import_from_disk('Person', csv_fd.name)

        # WHEN I run the import_history command
        command_output = StringIO()
        time_started = datetime.now()
        call_command('narwhal_import_history', stdout=command_output)

        # THEN I should see a listing showing the number, import time, filename, model, number of records,
        # and whether it succeeded or not.
        output = command_output.getvalue()
        self.assertIn('Person', output)
        self.assertIn('31', output)
        self.assertIn('32', output)
        self.assertIn('33', output)
        self.assertIn(os.path.basename(csv_fd.name), output)

    def test_import_history_detail_rows(self):
        # GIVEN an import has been run
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(4):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            do_import_from_disk('Person', csv_fd.name)

            # WHEN I pass the batch number as an argument to the import_history command
            command_output_stream = StringIO()
            batch_number = ImportBatch.objects.last().pk
            call_command('narwhal_import_history', batch_number, stdout=command_output_stream)

            # THEN I should see a listing showing the rows of the import
            command_output = command_output_stream.getvalue()
            for row in imported_records:
                self.assertIn(
                    row['name'],
                    command_output
                )

    def test_import_history_detail_error_rows(self):
        # GIVEN an import has been run with validation errors
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(4):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'BREAK'  # <-- bad value
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            do_import_from_disk('Person', csv_fd.name)

            # WHEN I pass the batch number as an argument to the import_history command
            command_output_stream = StringIO()
            batch_number = ImportBatch.objects.last().pk
            call_command('narwhal_import_history', batch_number, stdout=command_output_stream)

            # THEN I should see a listing showing the error rows of the import
            command_output = command_output_stream.getvalue()
            self.assertEqual(
                4,
                command_output.count("Enter a valid boolean value")
            )
