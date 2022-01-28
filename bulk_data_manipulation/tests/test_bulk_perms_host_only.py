from django.test import TestCase, TransactionTestCase
from io import StringIO
import tempfile
from django.core.management import call_command
from .common import import_record_with_extid
from uuid import uuid4
from core.models import Person
from bulk.models import BulkImport
import csv

# NOTICE: these tests are serving double duty in testing CsvBulkCommand in bulk_data_manipulation/common.py
# I didn't take the time to write better tests that isolate concerns. -TC


class BulkUpdateHostOnly(TestCase):
    """Functional test
    """

    def test_single_record(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is a record in the system
            new_person_name = f"person-name-{uuid4()}"
            person_record, _ = \
                import_record_with_extid(Person, {"name": new_person_name}, external_id='1638388421')
            Person.objects.get(name=new_person_name)
            # AND given there is a CSV file listing its external id, and the desired value of for_host_only
            row = {}
            row['id__external'] = '1638388421'
            row['for_host_only'] = 'checked'
            csv_writer = csv.DictWriter(csv_fd, row.keys())
            csv_writer.writeheader()
            csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the command with the target model and CSV file as positional arguments
            call_command('bulk_perms_host_only', 'core.models.Person', csv_fd.name, stdout=command_output)

            # THEN the record should be marked for_host_only=True
            self.assertEqual(
                True,
                Person.objects.get(pk=person_record.pk).for_host_only,
                msg=f"for_host_only not updated on test record"
            )

    def test_missing_record(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there was a record in the system that's been deleted
            new_person_name = f"person-name-{uuid4()}"
            person_record, _ = \
                import_record_with_extid(Person, {"name": new_person_name}, external_id='1638388421')
            Person.objects.get(name=new_person_name)
            # AND given there is a CSV file listing its external id, and the desired value of for_host_only
            row = {}
            row['id__external'] = '1638388421'
            row['for_host_only'] = 'checked'
            csv_writer = csv.DictWriter(csv_fd, row.keys())
            csv_writer.writeheader()
            csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            # ... delete the record from the db
            person_record.delete()

            # WHEN I run the command with the target model and CSV file as positional arguments
            # THEN an error should be printed on the screen
            call_command('bulk_perms_host_only', 'core.models.Person', csv_fd.name, stdout=command_output)
            self.assertIn(
                'does not exist',
                command_output.getvalue()
            )

    def test_missing_ext_id(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there was a record in the system who's external ID has been deleted
            new_person_name = f"person-name-{uuid4()}"
            person_record, external_id = \
                import_record_with_extid(Person, {"name": new_person_name}, external_id='1638388421')
            Person.objects.get(name=new_person_name)
            # AND given there is a CSV file listing its external id, and the desired value of for_host_only
            row = {}
            row['id__external'] = '1638388421'
            row['for_host_only'] = 'checked'
            csv_writer = csv.DictWriter(csv_fd, row.keys())
            csv_writer.writeheader()
            csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            # ... delete the record from the db
            BulkImport.objects.get(pk_imported_from=external_id).delete()

            # WHEN I run the command with the target model and CSV file as positional arguments
            # THEN an error should be printed on the screen
            call_command('bulk_perms_host_only', 'core.models.Person', csv_fd.name, stdout=command_output)
            self.assertIn(
                "Can't find external id",
                command_output.getvalue()
            )

    def test_multiple_records(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are a number of records in the system
            # AND given there is a CSV file listing their external ids, and the desired value of for_host_only
            csv_writer = csv.DictWriter(csv_fd, ['id__external', 'for_host_only'])
            csv_writer.writeheader()

            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                person_record, external_id = \
                    import_record_with_extid(Person, {"name": new_person_name, "for_host_only": False})
                Person.objects.get(name=new_person_name)
                row = {}
                row['id__external'] = external_id
                row['for_host_only'] = 'checked'
                csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the command with the target model and CSV file as positional arguments
            call_command('bulk_perms_host_only', 'core.models.Person', csv_fd.name, stdout=command_output)

            # THEN the records should be marked for_host_only=True
            self.assertEqual(
                10,
                Person.objects.all().count()
            )
            for record in Person.objects.all():
                self.assertEqual(
                    True,
                    record.for_host_only,
                    msg=f"for_host_only not updated on test record"
                )

    def test_empty_file_error(self):
        """Functional test: refuse to use an empty input file, warn me about it
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is an empty file with nothing on it
            pass
            # WHEN I execute the command on it
            call_command('bulk_perms_host_only', 'core.models.Person', csv_fd.name, stdout=command_output)

            # THEN it should return an error message to warn me
            self.assertIn("WARNING", command_output.getvalue())
            self.assertIn("empty", command_output.getvalue())

    def test_print_csv_row_number_of_errors(self):
        command_output = StringIO()

        # Given there's a CSV with an error on row 7
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            csv_writer = csv.DictWriter(csv_fd, ['id__external', 'for_host_only'])
            csv_writer.writeheader()

            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                person_record, external_id = \
                    import_record_with_extid(Person, {"name": new_person_name, "for_host_only": False})
                Person.objects.get(name=new_person_name)
                row = {}
                row['id__external'] = external_id
                row['for_host_only'] = 'checked'

                # ... insert error on 7th record
                if i == 6:  # zeroith index makes it 6
                    row['id__external'] = 'BREAK'
                    row['for_host_only'] = 'BREAK'

                csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # When I execute the command on it
            call_command('bulk_perms_host_only', 'core.models.Person', csv_fd.name, stdout=command_output)

            # Then it should return an error message that reads "Row 8" (record number plus 1 for the header)
            self.assertIn("Row 8", command_output.getvalue())


class AtomicRollbacks(TransactionTestCase):
    def test_on_error_rollback_db(self):
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are a number of records in the system
            # AND there is a CSV file listing their external ids, and the desired value of for_host_only
            # BUT ONE OF THE RECORDS HAS BEEN DELETED
            csv_writer = csv.DictWriter(csv_fd, ['id__external', 'for_host_only'])
            csv_writer.writeheader()

            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                person_record, external_id = \
                    import_record_with_extid(Person, {"name": new_person_name, "for_host_only": False})
                Person.objects.get(name=new_person_name)
                row = {}
                row['id__external'] = external_id
                row['for_host_only'] = 'checked'
                csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            Person.objects.first().delete()

            # WHEN I run the command with the target model and CSV file as positional arguments
            call_command('bulk_perms_host_only', 'core.models.Person', csv_fd.name, stdout=command_output)

            # THEN the output should say that it's rolling back
            #
            #
            self.assertIn("Undoing", command_output.getvalue())

            # AND the database should be in the state it was before calling the 'data_update' command
            for record in Person.objects.all():
                self.assertEqual(
                    False,
                    record.for_host_only,
                    msg=f"for_host_only updated on test record"
                )
