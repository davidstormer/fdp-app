import csv
import hashlib
import ipaddress
from datetime import datetime, timedelta
from unittest import skip

from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
from uuid import uuid4

from bulk.models import BulkImport
from core.models import Person, Incident
from functional_tests.common import FunctionalTestCase
from functional_tests.common_import_export import import_record_with_extid
from importer_narwhal.models import ImportBatch
from sourcing.models import Content
from supporting.models import TraitType, Trait


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

    def test_m2m_traits_export_natural_keys_via_person(self):
        # Given there are traits in the system linked to a person
        trait_type = TraitType.objects.create(name='trait-type-name-miscellanist')
        trait1 = Trait.objects.create(name='trait-auxamylase', type=trait_type)
        person = Person.objects.create(name="Test Person")
        person.traits.add(trait1)
        # When I export the Person records
        # Then I should see the trait VALUES in the export sheet
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = temp_dir + '/output.csv'
            # When I run the command
            command_output = StringIO()
            call_command('narwhal_export', 'Person', output_file, stdout=command_output)

            # Then there should be a csv file with the records in it
            with open(output_file, 'r') as file_fd:
                file_contents = file_fd.read()
                self.assertIn(
                    'auxamylase',
                    file_contents
                )

    def test_m2m_traits_export_natural_keys(self):
        # Given there are traits in the system linked to a person
        trait1 = Trait.objects.create(name='trait-auxamylase')
        person = Person.objects.create(name="Test Person")
        person.traits.add(trait1)
        # When I export the Person records
        # Then I should see the trait VALUES in the export sheet
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = temp_dir + '/output.csv'
            # When I run the command
            command_output = StringIO()
            call_command('narwhal_export', 'Trait', output_file, stdout=command_output)

            # Then there should be a csv file with the records in it
            with open(output_file, 'r') as file_fd:
                file_contents = file_fd.read()
                self.assertIn(
                    'auxamylase',
                    file_contents
                )

    def test_m2m_trait_types_export_natural_keys_via_trait(self):
        # Given there are traits in the system linked to a person
        trait_type = TraitType.objects.create(name='trait-type-name-miscellanist')
        trait1 = Trait.objects.create(name='trait-auxamylase', type=trait_type)
        person = Person.objects.create(name="Test Person")
        person.traits.add(trait1)
        # When I export the Person records
        # Then I should see the trait VALUES in the export sheet
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = temp_dir + '/output.csv'
            # When I run the command
            command_output = StringIO()
            call_command('narwhal_export', 'Trait', output_file, stdout=command_output)

            # Then there should be a csv file with the records in it
            with open(output_file, 'r') as file_fd:
                file_contents = file_fd.read()
                self.assertIn(
                    'miscellanist',
                    file_contents
                )

    # TODO: "get or create" logic on m2ms
    # https://stackoverflow.com/questions/32369984/django-import-export-new-values-in-foriegn-key-model
    @skip
    def test_bulk_edit_scenario_m2m_traits(self):
        # Given there are existing records in the system,
        # some with "to_edit" in their name
        existing_records = []
        for i in range(5):
            existing_records.append(import_record_with_extid(Person, {
                'name': f'Person record {uuid4()}',
                'traits': [Trait.objects.create(name=f'Test Trait {uuid4()}')],
            }))
        for i in range(5):
            existing_records.append(import_record_with_extid(Person, {
                'name': f'Person record to_edit {uuid4()}',
                'traits': [Trait.objects.create(name=f'Test Trait {uuid4()}')],
            }))

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

    def test_multiple_external_ids_on_single_record(self):
        """Because there's no unique constraint on external IDs..."""

        # Given there are two unique IDs (BulkImport) pointing to the same record
        bulk_import = import_record_with_extid(Person, {'name': f'Person record apophlegmatic'},
                                               external_id='External ID #1')
        BulkImport.objects.create(
            table_imported_to=Person.get_db_table(),
            pk_imported_to=bulk_import['record'].pk,
            pk_imported_from='External ID #2',
            data_imported='{}'  # make constraints happy...
        )

        # When I run an export
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file_name = temp_dir + '/bulk_edit_sheet.csv'
            call_command('narwhal_export', 'Person', output_file_name)

            # Then there should be an export file with the record in it
            with open(output_file_name, 'r') as file_fd:
                file_contents = file_fd.read()
                self.assertIn(
                    'apophlegmatic',
                    file_contents
                )
            # And it should contain BOTH external IDs that point to the record...
            # True story this actually happened once!
            with open(output_file_name, 'r') as file_fd:
                file_contents = file_fd.read()
                self.assertIn(
                    'External ID #1,External ID #2',
                    file_contents
                )


class ExportAccessLog(FunctionalTestCase):
    # Typical output: dict_keys(['id', 'user_agent', 'ip_address', 'username', 'http_accept', 'path_info',
    # 'attempt_time', 'logout_time'])
    def test_access_time(self):
        # Given someone has logged into the system
        admin_client = self.log_in(is_administrator=True)

        # When I run an export
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file_name = temp_dir + '/output.csv'
            call_command('narwhal_export', 'AccessLog', output_file_name)

            # Then I should see a record of them logging in
            with open(output_file_name, 'r') as file_fd:
                csv_reader = csv.DictReader(file_fd)

                row = next(csv_reader)
                access_time = row['attempt_time']
                self.assertAlmostEqual(
                    datetime.now(),
                    datetime.fromisoformat(access_time),
                    delta=timedelta(10)
                )

    def test_ip_address_hashed(self):
        # Given someone has logged into the system (from 127.0.0.1)
        admin_client = self.log_in(is_administrator=True)

        # When I run an export
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file_name = temp_dir + '/output.csv'
            call_command('narwhal_export', 'AccessLog', output_file_name)

            # Then I should see a hash instead of an IP address
            with open(output_file_name, 'r') as file_fd:
                csv_reader = csv.DictReader(file_fd)
                row = next(csv_reader)
                ip_address = row['ip_address'].strip()

                try:
                    ipaddress.ip_address(ip_address)
                    self.fail(f'IP address found in ip_address column: {ip_address}')
                except ValueError:
                    pass

                self.assertEqual(
                    ip_address,
                    hashlib.sha256('127.0.0.1'.encode('utf-8')).hexdigest()
                )

    def test_username_hashed(self):
        # Given someone has logged into the system (as noreply@gmail.com)
        admin_client = self.log_in_as('hello@example.com', is_administrator=True)

        # When I run an export
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file_name = temp_dir + '/output.csv'
            call_command('narwhal_export', 'AccessLog', output_file_name)

            # Then I should see a hash instead of an IP address
            with open(output_file_name, 'r') as file_fd:
                csv_reader = csv.DictReader(file_fd)
                row = next(csv_reader)
                username = row['username'].strip()

                self.assertNotIn(
                    'hello@example.com',
                    username,
                )

                self.assertEqual(
                    username,
                    hashlib.sha256('hello@example.com'.encode('utf-8')).hexdigest()
                )

    def test_is_administrator(self):
        """Test that a new 'is_administrator' field is present in the output"""
        # Given two ppl have logged into the system, first admin, second not admin
        admin_client = self.log_in_as('hello-admin@example.com', is_administrator=True)
        admin_client = self.log_in_as('hello-not-admin@example.com', is_administrator=False)

        # When I run an export
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file_name = temp_dir + '/output.csv'
            call_command('narwhal_export', 'AccessLog', output_file_name)

            with open(output_file_name, 'r') as file_fd:
                csv_reader = csv.DictReader(file_fd)

                # Then I should see a first row where is_administrator=TRUE
                row = next(csv_reader)
                is_administrator = row['is_administrator'].strip()
                self.assertEqual(
                    'TRUE',
                    is_administrator
                )

                # Then I should see a second row where is_administrator=FALSE
                row = next(csv_reader)
                is_administrator = row['is_administrator'].strip()
                self.assertEqual(
                    'FALSE',
                    is_administrator
                )
