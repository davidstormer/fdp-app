import csv

from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
from uuid import uuid4
from core.models import Person, Incident
from functional_tests.common_import_export import import_record_with_extid
from importer_narwhal.models import ImportBatch
from sourcing.models import Content


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

    def test_bulk_edit_scenario_person(self):
        # Given there are existing records in the system,
        # some with "to_edit" in their name
        existing_records = []
        for i in range(5):
            existing_records.append(import_record_with_extid(Person, {'name': f'Person record {uuid4()}'}))
        for i in range(5):
            existing_records.append(import_record_with_extid(Person, {'name': f'Person record to_edit {uuid4()}'}))

        # Belt, _and_ suspenders...?
        # self.assertEqual(
        #     5,
        #     Person.objects.filter(name__icontains='to_edit').count()
        # )

        # When I do an export, and edit the cells of the CSV, changing "to_edit" to "edited"
        # and then import the CSV.
        def search_replace(filename, search_for, replace_with):
            # Read in the file
            with open(filename, 'r') as file:
                filedata = file.read()

            # Replace the target string
            filedata = filedata.replace(search_for, replace_with)

            # Write the file out again
            with open(filename, 'w') as file:
                file.write(filedata)

        with tempfile.TemporaryDirectory() as temp_dir:
            bulk_edit_sheet_fn = temp_dir + '/bulk_edit_sheet.csv'
            call_command('narwhal_export', 'Person', bulk_edit_sheet_fn)

            search_replace(bulk_edit_sheet_fn, 'to_edit', 'edited')

            command_output = StringIO()
            call_command('narwhal_import', 'Person', bulk_edit_sheet_fn, stdout=command_output)

        # Then the records should be updated with the edits
        self.assertEqual(
            0,
            Person.objects.filter(name__icontains='to_edit').count(),
            msg="Records with 'to_edit' in their name still found in the system!"
        )
        self.assertEqual(
            5,
            Person.objects.filter(name__icontains='edited').count()
        )
        # And Then the history logs should show five updates and accompanying diffs
        history_command_output_stream = StringIO()
        batch_number = ImportBatch.objects.last().pk
        call_command('narwhal_import_history', batch_number, stdout=history_command_output_stream)
        history_command_output = history_command_output_stream.getvalue()

        self.assertEqual(
            5,
            history_command_output.count("update")
        )
        self.assertEqual(
            5,
            history_command_output.count("<del>to_</del><span>edit</span><ins>ed</ins>")
        )
        # And Then the history logs should not show edits to records that had no changes in the CSV
        self.assertEqual(
            5,
            history_command_output.count("skip")
        )

    def test_bulk_edit_scenario_content(self):
        # Given there are existing records in the system,
        # some with "to_edit" in their description
        existing_records = []
        for i in range(5):
            existing_records.append(import_record_with_extid(Content, {'description': f'Content record {uuid4()}'}))
        for i in range(5):
            existing_records.append(import_record_with_extid(Content, {'description': f'Content record to_edit {uuid4()}'}))

        # Belt, _and_ suspenders...?
        # self.assertEqual(
        #     5,
        #     Content.objects.filter(description__icontains='to_edit').count()
        # )

        # When I do an export, and edit the cells of the CSV, changing "to_edit" to "edited"
        # and then import the CSV.
        def search_replace(filename, search_for, replace_with):
            # Read in the file
            with open(filename, 'r') as file:
                filedata = file.read()

            # Replace the target string
            filedata = filedata.replace(search_for, replace_with)

            # Write the file out again
            with open(filename, 'w') as file:
                file.write(filedata)

        with tempfile.TemporaryDirectory() as temp_dir:
            bulk_edit_sheet_fn = temp_dir + '/bulk_edit_sheet.csv'
            call_command('narwhal_export', 'Content', bulk_edit_sheet_fn)

            search_replace(bulk_edit_sheet_fn, 'to_edit', 'edited')

            command_output = StringIO()
            call_command('narwhal_import', 'Content', bulk_edit_sheet_fn, stdout=command_output)

        # Then the records should be updated with the edits
        self.assertEqual(
            0,
            Content.objects.filter(description__icontains='to_edit').count(),
            msg="Records with 'to_edit' in their description still found in the system!"
        )
        self.assertEqual(
            5,
            Content.objects.filter(description__icontains='edited').count()
        )
        # And Then the history logs should show five updates and accompanying diffs
        history_command_output_stream = StringIO()
        batch_number = ImportBatch.objects.last().pk
        call_command('narwhal_import_history', batch_number, stdout=history_command_output_stream)
        history_command_output = history_command_output_stream.getvalue()

        self.assertEqual(
            5,
            history_command_output.count("update")
        )
        self.assertEqual(
            5,
            history_command_output.count("<del>to_</del><span>edit</span><ins>ed</ins>")
        )
        # And Then the history logs should not show edits to records that had no changes in the CSV
        self.assertEqual(
            5,
            history_command_output.count("skip")
        )

    def test_bulk_edit_scenario_incident(self):
        # Given there are existing records in the system,
        # some with "to_edit" in their description
        existing_records = []
        for i in range(5):
            existing_records.append(import_record_with_extid(Incident, {'description': f'Incident record {uuid4()}'}))
        for i in range(5):
            existing_records.append(import_record_with_extid(Incident, {'description': f'Incident record to_edit {uuid4()}'}))

        # Belt, _and_ suspenders...?
        # self.assertEqual(
        #     5,
        #     Incident.objects.filter(description__icontains='to_edit').count()
        # )

        # When I do an export, and edit the cells of the CSV, changing "to_edit" to "edited"
        # and then import the CSV.
        def search_replace(filename, search_for, replace_with):
            # Read in the file
            with open(filename, 'r') as file:
                filedata = file.read()

            # Replace the target string
            filedata = filedata.replace(search_for, replace_with)

            # Write the file out again
            with open(filename, 'w') as file:
                file.write(filedata)

        with tempfile.TemporaryDirectory() as temp_dir:
            bulk_edit_sheet_fn = temp_dir + '/bulk_edit_sheet.csv'
            call_command('narwhal_export', 'Incident', bulk_edit_sheet_fn)

            search_replace(bulk_edit_sheet_fn, 'to_edit', 'edited')

            command_output = StringIO()
            call_command('narwhal_import', 'Incident', bulk_edit_sheet_fn, stdout=command_output)

        # Then the records should be updated with the edits
        self.assertEqual(
            0,
            Incident.objects.filter(description__icontains='to_edit').count(),
            msg="Records with 'to_edit' in their description still found in the system!"
        )
        self.assertEqual(
            5,
            Incident.objects.filter(description__icontains='edited').count()
        )
        # And Then the history logs should show five updates and accompanying diffs
        history_command_output_stream = StringIO()
        batch_number = ImportBatch.objects.last().pk
        call_command('narwhal_import_history', batch_number, stdout=history_command_output_stream)
        history_command_output = history_command_output_stream.getvalue()

        self.assertEqual(
            5,
            history_command_output.count("update")
        )
        self.assertEqual(
            5,
            history_command_output.count("<del>to_</del><span>edit</span><ins>ed</ins>")
        )
        # And Then the history logs should not show edits to records that had no changes in the CSV
        self.assertEqual(
            5,
            history_command_output.count("skip")
        )
