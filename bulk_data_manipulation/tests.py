import pdb

from django.test import LiveServerTestCase, SimpleTestCase, TransactionTestCase
from core.models import Person, PersonIdentifier, Grouping
from supporting.models import PersonIdentifierType, County, State
from bulk.models import BulkImport
from pprint import pprint
import logging
import csv
import json
import tempfile

from io import StringIO
from django.core.management import call_command
from django.test import TestCase

from uuid import uuid4
import copy
from unittest.mock import patch

from .management.commands.bulk_update_groups import get_record_from_external_id, ExternalIdMissing, RecordMissing, \
    ExternalIdDuplicates, FIELDNAMES, parse_comma_delimited_values, get_records_from_extid_cdv, import_record_with_extid


def csv_to_list_dict(csv_reader):
    """Utility for making test data structures for inserting into tests
    """
    data = []
    for i, row in enumerate(csv_reader):
        data.append(row)
    pprint(data)


class DataUpdateTest(TestCase):
    def test_data_update(self):
        """Functional test: Import data
        """
        out = StringIO()
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are a set of existing records in the system (with external ids)
            #
            #
            imported_records_log = []
            #  Make parent group first
            parent_grouping_name_value = f"{uuid4()}"
            parent_group_record, parent_grouping_external_id = import_record_with_extid(Grouping, {
                "name": parent_grouping_name_value,
            })
            #  And make a county to assign
            old_county, old_county_external_id = import_record_with_extid(County, {
                "name": f"{uuid4()}",
                "state": State.objects.create(name=f"{uuid4()}")
            })
            #  Then make ten child groups, in said county
            for i in range(10):
                grouping_name_value = f"{uuid4()}"
                group_record, grouping_external_id = import_record_with_extid(Grouping, {
                    "name": grouping_name_value,
                    "belongs_to_grouping": parent_group_record,
                })
                group_record.counties.add(old_county)
                imported_records_log.append(
                    {
                        "pk": group_record.pk,
                        "Grouping.external_id": grouping_external_id,
                        "Grouping.name": grouping_name_value,
                        "Grouping.belongs_to_grouping_extid": parent_grouping_external_id,
                        "Grouping.counties_extid_cdv": old_county_external_id,
                    }
                )
            # and there is a spreadsheet of new values for those records (referenced by external ids)
            # and new records corresponding to new references made in the spreadsheet
            #
            #  Make new group to put the child groups under
            new_parent_grouping_name_value = f"{uuid4()}"
            new_parent_group_record, new_parent_grouping_external_id = import_record_with_extid(Grouping, {
                "name": new_parent_grouping_name_value,
            })
            #  Make a new county to set them to instead
            new_county, new_county_external_id = import_record_with_extid(County, {
                "name": str(uuid4()),
                "state": State.objects.create(name=f"{uuid4()}"),
            })

            updates_sheet = copy.deepcopy(imported_records_log)
            for row in updates_sheet:
                row['Grouping.name'] = f"{uuid4()}"
                row['Grouping.belongs_to_grouping_extid'] = new_parent_grouping_external_id
                row["Grouping.counties_extid_cdv"] = new_county_external_id
                del row['pk']
            csv_writer = csv.DictWriter(csv_fd, FIELDNAMES)
            csv_writer.writeheader()
            for row in updates_sheet:
                csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem

            # WHEN I call the data_update command pointed at the CSV
            #
            #
            call_command('bulk_update_groups', csv_fd.name, stdout=out)

            # THEN the records in the system should have the new values, and not the old values
            #
            #
            for i, imported_record_log in enumerate(imported_records_log):
                updated_record = Grouping.objects.get(pk=imported_record_log['pk'])
                # Name value
                self.assertNotEqual(updated_record.name, imported_record_log['Grouping.name'])
                self.assertEqual(updated_record.name, updates_sheet[i]['Grouping.name'])
                # Belongs to
                old_parent_pk = get_record_from_external_id(
                        Grouping,
                        imported_record_log['Grouping.belongs_to_grouping_extid']).pk
                self.assertNotEqual(
                    updated_record.belongs_to_grouping.pk,
                    old_parent_pk,
                    msg="belongs_to_grouping hasn't been updated!")
                new_parent_pk = get_record_from_external_id(
                        Grouping,
                        updates_sheet[i]['Grouping.belongs_to_grouping_extid']).pk
                self.assertEqual(
                    updated_record.belongs_to_grouping.pk,
                    new_parent_pk,
                    msg="belongs_to_grouping doesn't match what it's supposed to have been updated to")
                # County
                self.assertLessEqual(len(updated_record.counties.values()), 1)
                self.assertNotEqual(updated_record.counties.values()[0]['id'], old_county.pk)
                self.assertEqual(updated_record.counties.values()[0]['id'], new_county.pk)
                self.assertEqual(updated_record.counties.values()[0]['name'], new_county.name)

    def test_data_update_csv_not_found(self):
        command_output = StringIO()
        filename = f"{uuid4()}.csv"
        call_command('bulk_update_groups', filename, stdout=command_output)
        self.assertIn(f"Couldn't find file {filename}. Quitting...", command_output.getvalue())

    def test_get_record_from_external_id_missing_external_id(self):
        # GIVEN there is a record in the system, but no external id
        person_record = Person.objects.create(name=f"{uuid4()}")
        external_id = f"{uuid4()}"
        bulk_import_record = BulkImport.objects.create(
            pk_imported_from=external_id,
            pk_imported_to=person_record.pk,
            data_imported="{}",
            table_imported_to=Person.get_db_table()
        )
        bulk_import_record.delete()
        # WHEN I call get_record_from_external_id on it
        # THEN I should see an ExternalIdMissing exception
        with self.assertRaises(ExternalIdMissing):
            get_record_from_external_id(Person, "obsolete-id-you'll-never-find-me")

    def test_get_record_from_external_id_missing_record(self):
        # GIVEN there is an external id, but the record is missing from the system
        person_record = Person.objects.create(name=f"{uuid4()}")
        external_id = f"{uuid4()}"
        BulkImport.objects.create(
            pk_imported_from=external_id,
            pk_imported_to=person_record.pk,
            data_imported="{}",
            table_imported_to=Person.get_db_table()
        )
        person_record.delete()
        # WHEN I call get_record_from_external_id on it
        # THEN I should see a RecordMissing exception
        with self.assertRaises(RecordMissing):
            get_record_from_external_id(Person, external_id)

    def test_get_record_from_external_id_missing_record_and_external_id(self):
        # GIVEN there is neither a record nor an external id
        # WHEN I call get_record_from_external_id on it
        # THEN I should see an ExternalIdMissing exception
        # GIVEN there is an external id, but the record is missing from the system
        person_record = Person.objects.create(name=f"{uuid4()}")
        external_id = f"{uuid4()}"
        bulk_import_record = BulkImport.objects.create(
            pk_imported_from=external_id,
            pk_imported_to=person_record.pk,
            data_imported="{}",
            table_imported_to=Person.get_db_table()
        )
        person_record.delete()
        bulk_import_record.delete()
        # WHEN I call get_record_from_external_id on it
        # THEN I should see an ExternalIdMissing exception
        with self.assertRaises(ExternalIdMissing):
            get_record_from_external_id(Person, external_id)

    def test_get_record_from_external_id_duplicate_external_ids(self):
        # GIVEN there are duplicate external ids (because there's currently no unique constraint 2021-11-19)
        person_record = Person.objects.create(name=f"{uuid4()}")
        person_record2 = Person.objects.create(name=f"{uuid4()}")
        external_id = f"{uuid4()}"
        bulk_import_record = BulkImport.objects.create(
            pk_imported_from=external_id,
            pk_imported_to=person_record.pk,
            data_imported="{}",
            table_imported_to=Person.get_db_table()
        )
        bulk_import_record = BulkImport.objects.create(
            pk_imported_from=external_id,
            pk_imported_to=person_record2.pk,
            data_imported="{}",
            table_imported_to=Person.get_db_table()
        )
        # WHEN I call get_record_from_external_id on it
        # THEN I should see an ExternalIdDuplicates exception
        with self.assertRaises(ExternalIdDuplicates):
            get_record_from_external_id(Person, external_id)

    def test_parse_comma_delimited_values(self):
        self.assertEqual(
            parse_comma_delimited_values("hello, world"),
            ['hello', 'world']
        )

    def test_get_records_from_extid_cdv(self):
        state = State.objects.create(name=str(uuid4()))
        county1 = County.objects.create(name=str(uuid4()), state=state)
        BulkImport.objects.create(
            pk_imported_from='314159',
            pk_imported_to=county1.pk,
            data_imported="{}",
            table_imported_to=County.get_db_table()
        )
        county2 = County.objects.create(name=str(uuid4()), state=state)
        BulkImport.objects.create(
            pk_imported_from='90210',
            pk_imported_to=county2.pk,
            data_imported="{}",
            table_imported_to=County.get_db_table()
        )
        self.assertEqual(
            [county1, county2],
            get_records_from_extid_cdv(County, '314159, 90210')
        )

    def test_import_record_with_extid(self):
        record, external_id = import_record_with_extid(Person, {"name": "Hello World 1637354434"})
        self.assertEqual(1, len(Person.objects.all()))
        self.assertEqual(
            record,
            Person.objects.get(name="Hello World 1637354434")
        )
        self.assertEqual(
            record,
            get_record_from_external_id(Person, external_id)
        )

    def test_on_error_print_rownum(self):
        """Functional test: print CSV row number
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are a set of existing records in the system (with external ids)
            #
            #
            imported_records_log = []
            #  Make parent group first
            parent_grouping_name_value = f"old-parentgroupname-{uuid4()}"
            parent_group_record, parent_grouping_external_id = import_record_with_extid(Grouping, {
                "name": parent_grouping_name_value,
            })
            #  And make a county to assign
            old_county, old_county_external_id = import_record_with_extid(County, {
                "name": f"{uuid4()}",
                "state": State.objects.create(name=f"old-state-{uuid4()}")
            })
            #  Then make ten child groups, in said county
            for i in range(10):
                grouping_name_value = f"old-groupname-{uuid4()}"
                group_record, grouping_external_id = import_record_with_extid(Grouping, {
                    "name": grouping_name_value,
                    "belongs_to_grouping": parent_group_record,
                })
                group_record.counties.add(old_county)
                imported_records_log.append(
                    {
                        "pk": group_record.pk,
                        "Grouping.external_id": grouping_external_id,
                        "Grouping.name": grouping_name_value,
                        "Grouping.belongs_to_grouping_extid": parent_grouping_external_id,
                        "Grouping.counties_extid_cdv": old_county_external_id,
                    }
                )
            # AND there is a spreadsheet of new values for those records (referenced by external ids)
            # AND new records corresponding to new references made in the spreadsheet
            #
            #  Make new group to put the child groups under
            new_parent_grouping_name_value = f"new-groupname-{uuid4()}"
            new_parent_group_record, new_parent_grouping_external_id = import_record_with_extid(Grouping, {
                "name": new_parent_grouping_name_value,
            })
            #  Make a new county to set them to instead
            new_county, new_county_external_id = import_record_with_extid(County, {
                "name": f"newname-uuid4()",
                "state": State.objects.create(name=f"new-statename-{uuid4()}"),
            })

            updates_sheet = copy.deepcopy(imported_records_log)
            for row in updates_sheet:
                row['Grouping.name'] = f"new-groupname-{uuid4()}"
                row['Grouping.belongs_to_grouping_extid'] = new_parent_grouping_external_id
                row["Grouping.counties_extid_cdv"] = new_county_external_id
                del row['pk']
            csv_writer = csv.DictWriter(csv_fd, FIELDNAMES)
            csv_writer.writeheader()
            for row in updates_sheet:
                csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem

            num_extids_pre_execution = len(BulkImport.objects.all())

            # AND ONE OF THE RECORDS TO BE UPDATED HAS BEEN DELETED ###########################################
            Grouping.objects.get(pk=imported_records_log[3]['pk']).delete()
            del imported_records_log[3]
            # WHEN I call the data_update command pointed at the CSV
            #
            #
            call_command('bulk_update_groups', csv_fd.name, stdout=command_output)

        # THEN the output should report an error with the row number
        #
        #
        self.assertIn("Row:5 :", command_output.getvalue())  # 3 + zeroth index + header line = 5


class AtomicRollbacks(TransactionTestCase):
    def test_data_update_on_error_rollback_db(self):
        """Functional test: Rollback on error
        """
        command_output = StringIO()

        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are a set of existing records in the system (with external ids)
            #
            #
            imported_records_log = []
            #  Make parent group first
            parent_grouping_name_value = f"old-parentgroupname-{uuid4()}"
            parent_group_record, parent_grouping_external_id = import_record_with_extid(Grouping, {
                "name": parent_grouping_name_value,
            })
            #  And make a county to assign
            old_county, old_county_external_id = import_record_with_extid(County, {
                "name": f"{uuid4()}",
                "state": State.objects.create(name=f"old-state-{uuid4()}")
            })
            #  Then make ten child groups, in said county
            for i in range(10):
                grouping_name_value = f"old-groupname-{uuid4()}"
                group_record, grouping_external_id = import_record_with_extid(Grouping, {
                    "name": grouping_name_value,
                    "belongs_to_grouping": parent_group_record,
                })
                group_record.counties.add(old_county)
                imported_records_log.append(
                    {
                        "pk": group_record.pk,
                        "Grouping.external_id": grouping_external_id,
                        "Grouping.name": grouping_name_value,
                        "Grouping.belongs_to_grouping_extid": parent_grouping_external_id,
                        "Grouping.counties_extid_cdv": old_county_external_id,
                    }
                )
            # AND there is a spreadsheet of new values for those records (referenced by external ids)
            # AND new records corresponding to new references made in the spreadsheet
            #
            #  Make new group to put the child groups under
            new_parent_grouping_name_value = f"new-groupname-{uuid4()}"
            new_parent_group_record, new_parent_grouping_external_id = import_record_with_extid(Grouping, {
                "name": new_parent_grouping_name_value,
            })
            #  Make a new county to set them to instead
            new_county, new_county_external_id = import_record_with_extid(County, {
                "name": f"newname-uuid4()",
                "state": State.objects.create(name=f"new-statename-{uuid4()}"),
            })

            updates_sheet = copy.deepcopy(imported_records_log)
            for row in updates_sheet:
                row['Grouping.name'] = f"new-groupname-{uuid4()}"
                row['Grouping.belongs_to_grouping_extid'] = new_parent_grouping_external_id
                row["Grouping.counties_extid_cdv"] = new_county_external_id
                del row['pk']
            csv_writer = csv.DictWriter(csv_fd, FIELDNAMES)
            csv_writer.writeheader()
            for row in updates_sheet:
                csv_writer.writerow(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem

            num_extids_pre_execution = len(BulkImport.objects.all())

            # AND ONE OF THE RECORDS TO BE UPDATED HAS BEEN DELETED ###########################################
            Grouping.objects.get(pk=imported_records_log[3]['pk']).delete()
            del imported_records_log[3]
            # WHEN I call the data_update command pointed at the CSV
            #
            #
            call_command('bulk_update_groups', csv_fd.name, stdout=command_output)

        # THEN the output should report an error
        #
        #
        self.assertIn("Undoing", command_output.getvalue())

        # AND the database should be in the state it was before calling the 'data_update' command
        self.assertEqual(num_extids_pre_execution, len(BulkImport.objects.all()))

        for i, imported_record_log in enumerate(imported_records_log):
            updated_record = Grouping.objects.get(pk=imported_record_log['pk'])

            # Name value
            self.assertEqual(updated_record.name, imported_record_log['Grouping.name'])
            self.assertNotEqual(updated_record.name, updates_sheet[i]['Grouping.name'])
            # Belongs to
            old_parent_pk = get_record_from_external_id(
                Grouping,
                imported_record_log['Grouping.belongs_to_grouping_extid']).pk
            self.assertEqual(
                updated_record.belongs_to_grouping.pk,
                old_parent_pk,
                msg="belongs_to_grouping hasn't been updated!")
            new_parent_pk = get_record_from_external_id(
                Grouping,
                updates_sheet[i]['Grouping.belongs_to_grouping_extid']).pk
            self.assertNotEqual(
                updated_record.belongs_to_grouping.pk,
                new_parent_pk,
                msg="belongs_to_grouping doesn't match what it's supposed to have been updated to")
            # County
            self.assertLessEqual(len(updated_record.counties.values()), 1)
            self.assertEqual(updated_record.counties.values()[0]['id'], old_county.pk)
            self.assertNotEqual(updated_record.counties.values()[0]['id'], new_county.pk)
            self.assertNotEqual(updated_record.counties.values()[0]['name'], new_county.name)
