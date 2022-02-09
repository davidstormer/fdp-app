import reversion
from django.test import TestCase, TransactionTestCase
from io import StringIO
import tempfile
from django.core.management import call_command
from .common import import_record_with_extid
from uuid import uuid4
from core.models import Person
from bulk_data_manipulation.management.commands.bulk_delete import get_model_from_import_string, delete_imported_record
from bulk_data_manipulation.common import get_record_from_external_id, ExternalIdMissing, RecordMissing
from core.models import Person
from bulk.models import BulkImport
from reversion.models import Version
import csv


class BulkDelete(TestCase):

    def test_bulk_delete_success(self):
        """Functional test
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are records in the system, but one of them has been deleted
            new_person_names = []
            new_external_ids = []
            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                new_external_id = f"external-id-{uuid4()}"
                import_record_with_extid(Person, {"name": new_person_name}, external_id=new_external_id)
                new_person_names.append(new_person_name)
                new_external_ids.append(new_external_id)
            for new_person_name in new_person_names:
                Person.objects.get(name=new_person_name)
            # and given there is a file listing their external ids
            for external_id in new_external_ids:
                csv_fd.write(f"{external_id}\n")
            csv_fd.flush()  # Make sure the file is actually written to disk!

            # WHEN I run the command
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, '--force', stdout=command_output)

            # THEN all the records should be removed from the system.
            self.assertEqual(
                0,
                Person.objects.all().count()
            )

            # and all of the BulkImport records (external ids) should also be removed from the system.
            self.assertEqual(
                0,
                BulkImport.objects.all().count()
            )

    def test_bulk_delete_verbose(self):
        """Functional test
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are records in the system
            new_person_names = []
            new_external_ids = []
            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                new_external_id = f"external-id-{uuid4()}"
                import_record_with_extid(Person, {"name": new_person_name}, external_id=new_external_id)
                new_person_names.append(new_person_name)
                new_external_ids.append(new_external_id)
            for new_person_name in new_person_names:
                Person.objects.get(name=new_person_name)
            # and given there is a file listing their external ids
            for external_id in new_external_ids:
                csv_fd.write(f"{external_id}\n")
            csv_fd.flush()  # Make sure the file is actually written to disk!

            # WHEN I run the command with a verbosity greater than 1
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, '--verbosity=2', stdout=command_output)

            # THEN the output should say that the records were deleted
            for ext_id in new_external_ids:
                self.assertIn(f"Deleted: <class 'core.models.Person'>|{ext_id}",
                              command_output.getvalue())

    def test_bulk_delete_single_record(self):
        """Functional test: delete single record from an input file
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is a record in the system
            new_person_name = f"person-name-{uuid4()}"
            import_record_with_extid(Person, {"name": new_person_name}, external_id='1638388421')
            Person.objects.get(name=new_person_name)
            # AND given there is a file listing its external id
            csv_fd.write('1638388421\n')
            csv_fd.flush()
            # WHEN I run the command with the file as a positional argument
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, stdout=command_output)
            # THEN the record should be removed from the system
            with self.assertRaises(Person.DoesNotExist) as _:
                Person.objects.get(name=new_person_name)

    def test_bulk_delete_multiple_records(self):
        """Functional test: delete records from an input file
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are records in the system
            new_person_names = []
            new_external_ids = []
            for i in range(3):
                new_person_name = f"person-name-{uuid4()}"
                new_external_id = f"external-id-{uuid4()}"
                import_record_with_extid(Person, {"name": new_person_name}, external_id=new_external_id)
                new_person_names.append(new_person_name)
                new_external_ids.append(new_external_id)
            for new_person_name in new_person_names:
                Person.objects.get(name=new_person_name)
            # AND given there is a file listing their external ids
            for external_id in new_external_ids:
                csv_fd.write(f"{external_id}\n")
            csv_fd.flush()  # Make sure the file is actually written to disk!
            # WHEN I run the command with the file as a positional argument
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, stdout=command_output)
            # THEN the records should be removed from the system
            with self.assertRaises(Person.DoesNotExist) as _:
                for new_person_name in new_person_names:
                    Person.objects.get(name=new_person_name)

    def test_bulk_delete_skip_records_with_revisions_no_revisions(self):
        """Functional test
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are records in the system
            new_person_names = []
            new_external_ids = []
            for i in range(3):
                new_person_name = f"person-name-{uuid4()}"
                new_external_id = f"external-id-{uuid4()}"
                import_record_with_extid(Person, {"name": new_person_name}, external_id=new_external_id)
                new_person_names.append(new_person_name)
                new_external_ids.append(new_external_id)
            for new_person_name in new_person_names:
                Person.objects.get(name=new_person_name)
            # and given there is a file listing their external ids
            for external_id in new_external_ids:
                csv_fd.write(f"{external_id}\n")
            csv_fd.flush()  # Make sure the file is actually written to disk!
            # AND NO REVISIONS HAVE BEEN MADE TO THE RECORDS
            pass
            # WHEN I run the command with arguments to skip records with revisions
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, '--skip-revisions=1', stdout=command_output)
            # THEN all the records should be removed from the system.
            self.assertEqual(
                0,
                Person.objects.all().count()
            )

    def test_bulk_delete_skip_records_with_revisions(self):
        """Functional test
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are records in the system
            new_person_names = []
            new_external_ids = []
            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                new_external_id = f"external-id-{uuid4()}"
                import_record_with_extid(Person, {"name": new_person_name}, external_id=new_external_id)
                new_person_names.append(new_person_name)
                new_external_ids.append(new_external_id)
            for new_person_name in new_person_names:
                Person.objects.get(name=new_person_name)
            # and given there is a file listing their external ids
            for external_id in new_external_ids:
                csv_fd.write(f"{external_id}\n")
            csv_fd.flush()  # Make sure the file is actually written to disk!
            # AND one of the records has been revised
            with reversion.create_revision():
                record_to_revise = Person.objects.all()[2]
                record_to_revise.name = "REVISED NAME"
                record_to_revise.save()

            # WHEN I run the command with arguments to skip records with revisions
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, '--skip-revisions=1', stdout=command_output)

            # THEN I should see a message about a skipped record
            self.assertIn("Skipping", command_output.getvalue())

            # THEN all the records except for the revised one should be removed from the system.
            self.assertEqual(
                1,
                Person.objects.all().count()
            )
            Person.objects.get(pk=record_to_revise.pk)

    def test_bulk_delete_force_mode(self):
        """Functional test
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are records in the system, but one of them has been deleted
            new_person_names = []
            new_external_ids = []
            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                new_external_id = f"external-id-{uuid4()}"
                import_record_with_extid(Person, {"name": new_person_name}, external_id=new_external_id)
                new_person_names.append(new_person_name)
                new_external_ids.append(new_external_id)
            for new_person_name in new_person_names:
                Person.objects.get(name=new_person_name)
            # and given there is a file listing their external ids
            for external_id in new_external_ids:
                csv_fd.write(f"{external_id}\n")
            csv_fd.flush()  # Make sure the file is actually written to disk!
            # AND one of the records has been deleted
            Person.objects.all()[2].delete()

            # WHEN I run the command with the "--force" flag
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, '--force', stdout=command_output)

            # THEN all the records should be removed from the system.
            self.assertEqual(
                0,
                Person.objects.all().count()
            )

            # But I should still get warnings about the missing records
            self.assertIn("Record does not exist", command_output.getvalue())
            # And I should not get a message about rolling back
            self.assertNotIn("Undoing", command_output.getvalue())

    def test_bulk_delete_keep_external_ids(self):
        """Functional test
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are records in the system
            new_person_names = []
            new_external_ids = []
            for i in range(10):
                new_person_name = f"person-name-{uuid4()}"
                new_external_id = f"external-id-{uuid4()}"
                import_record_with_extid(Person, {"name": new_person_name}, external_id=new_external_id)
                new_person_names.append(new_person_name)
                new_external_ids.append(new_external_id)
            for new_person_name in new_person_names:
                Person.objects.get(name=new_person_name)
            # and given there is a file listing their external ids
            for external_id in new_external_ids:
                csv_fd.write(f"{external_id}\n")
            csv_fd.flush()  # Make sure the file is actually written to disk!

            # WHEN I run the command with the "--keep-ext-ids" flag
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, '--keep-ext-ids', stdout=command_output)

            # THEN all the external ids (bulk imports) should still be there
            self.assertEqual(
                10,
                BulkImport.objects.all().count()
            )

    def test_get_model_from_import_string(self):
        self.assertEqual(
            get_model_from_import_string('core.models.Person'),
            Person
        )

    def test_delete_imported_record_success(self):
        # GIVEN there was a record imported into the system
        person_name = f"person-name-{uuid4()}"
        person_ext_id = f"ext-id-{uuid4()}"
        new_person_record = import_record_with_extid(Person, {"name": person_name}, external_id=person_ext_id)
        self.assertEqual(
            new_person_record[0],
            get_record_from_external_id(Person, new_person_record[1])
        )

        # WHEN I call test_delete_imported_record() on it
        delete_imported_record(Person, new_person_record[1])

        # THEN the record should be deleted from the system
        with self.assertRaises(Person.DoesNotExist) as _:
            Person.objects.get(name=person_name)
        # AND the external_id should still be left
        bulk_import_record = BulkImport.objects.get(
          pk_imported_from=new_person_record[1],
          )

    def test_delete_imported_record_success_ext_id_too(self):
        # GIVEN there was a record imported into the system
        person_name = f"person-name-{uuid4()}"
        person_ext_id = f"ext-id-{uuid4()}"
        new_person_record = import_record_with_extid(Person, {"name": person_name}, external_id=person_ext_id)
        self.assertEqual(
            new_person_record[0],
            get_record_from_external_id(Person, new_person_record[1])
        )

        # WHEN I call test_delete_imported_record() on it
        delete_imported_record(Person, new_person_record[1], delete_external_id=True)

        # THEN the record should be deleted from the system
        with self.assertRaises(Person.DoesNotExist) as _:
            Person.objects.get(name=person_name)
        # AND the external_id should still be gone
        with self.assertRaises(BulkImport.DoesNotExist) as _:
            bulk_import_record = BulkImport.objects.get(
              pk_imported_from=new_person_record[1],
              )

    def test_delete_imported_record_missing_record(self):
        # GIVEN there was a record imported into the system
        person_name = f"person-name-{uuid4()}"
        person_ext_id = f"ext-id-{uuid4()}"
        new_person_record = import_record_with_extid(Person, {"name": person_name}, external_id=person_ext_id)
        self.assertEqual(
            new_person_record[0],
            get_record_from_external_id(Person, new_person_record[1])
        )
        # AND THE RECORD IS DELETED -- but not the external id, btw
        new_person_record[0].delete()

        # WHEN I call test_delete_imported_record() on it
        # THEN an error should be raised
        with self.assertRaises(RecordMissing) as _:
            delete_imported_record(Person, new_person_record[1])

    def test_delete_imported_record_missing_ext_id(self):
        # GIVEN there was a record imported into the system
        person_name = f"person-name-{uuid4()}"
        person_ext_id = f"ext-id-{uuid4()}"
        new_person_record = import_record_with_extid(Person, {"name": person_name}, external_id=person_ext_id)
        self.assertEqual(
            new_person_record[0],
            get_record_from_external_id(Person, new_person_record[1])
        )
        # AND THE EXTERNAL ID IS DELETED -- but not the record itself, btw
        bulk_import_record = BulkImport.objects.get(
          pk_imported_from=new_person_record[1],
          )
        bulk_import_record.delete()

        # WHEN I call test_delete_imported_record() on it
        # THEN an error should be raised
        with self.assertRaises(ExternalIdMissing) as _:
            delete_imported_record(Person, new_person_record[1])

    def test_bulk_delete_empty_file_error(self):
        """Functional test: refuse to use an empty input file, warn me about it
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there is an empty file with nothing on it
            pass
            # WHEN I execute the command on it
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, stdout=command_output)

            # THEN it should return an error message to warn me
            self.assertIn("WARNING", command_output.getvalue())
            self.assertIn("empty", command_output.getvalue())


class AtomicRollbacks(TransactionTestCase):
    def test_bulk_delete_on_error_rollback_db(self):
        """Functional test: Rollback on error
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are a set of existing records in the system (with external ids)
            #
            #
            imported_records_log = []
            for i in range(10):
                person_name = f"person-name-{uuid4()}"
                person_ext_id = f"ext-id-{uuid4()}"
                new_person_record = import_record_with_extid(Person, {"name": person_name}, external_id=person_ext_id)
                imported_records_log.append({
                    "Person.pk": new_person_record[0].pk,
                    "Person.name": person_name,
                    "Person.external_id": person_ext_id
                })
            # AND given there is a file listing their external ids
            for record in imported_records_log:
                csv_fd.write(f"{record['Person.external_id']}\n"); csv_fd.flush()  # <- ACTUALLY WRITE TO DISK

            # AND ONE OF THE RECORDS TO BE DELETED HAS ALREADY BEEN DELETED ###############################
            Person.objects.get(pk=imported_records_log[3]['Person.pk']).delete()

            # WHEN I call the bulk_delete command pointed at the CSV
            #
            #
            call_command('bulk_delete', 'core.models.Person', csv_fd.name, stdout=command_output)

        # THEN the output should say that it's rolling back
        #
        #
        self.assertIn("Undoing", command_output.getvalue())

        # AND the database should be in the state it was before calling the 'data_update' command
        self.assertEqual(
            len(Person.objects.all()),
            len(imported_records_log) - 1  # Minus the one deleted record
        )
