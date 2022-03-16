import csv

from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
from uuid import uuid4
from core.models import Person
from functional_tests.common_import_export import import_record_with_extid


class NarwhalExportCommand(TestCase):
    """Functional tests
    """

    def test_export_success_scenario(self):
        # Given there are existing records in the system
        existing_records = []
        for i in range(5):
            existing_records.append(import_record_with_extid(Person, {'name': f'Person record {uuid4()}'}))
        # and Given there's an import sheet that references them by pk
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = temp_dir + '/output.csv'
            # When I run the command
            command_output = StringIO()
            call_command('narwhal_export', 'Person', output_file, stdout=command_output)

            # Then there should be a csv file with the records in it
            with open(output_file, 'r') as file_fd:
                file_contents = file_fd.read()
                for existing_record in existing_records:
                    self.assertIn(
                        existing_record['record'].name,
                        file_contents
                    )
                    self.assertIn(
                        existing_record['external_id'],
                        file_contents,
                        msg="External IDs missing from csv output"
                    )
