from core.models import Person, PersonIdentifier, Grouping
import csv
import tempfile

from io import StringIO
from django.core.management import call_command
from django.test import TestCase

from uuid import uuid4
import copy

from bulk_data_manipulation.management.commands.bulk_add_identifiers import FIELDNAMES
from bulk_data_manipulation.common import ExternalIdMissing, RecordMissing, ExternalIdDuplicates, ImportErrors
from bulk_data_manipulation.common import get_record_from_external_id
from bulk_data_manipulation.tests.common import import_record_with_extid


class DataUpdateTest(TestCase):
    def test_data_update(self):
        """Functional test: Import data
        """
        out = StringIO()
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            # GIVEN there are a set of existing Person records in the system (with external ids)
            #
            #
            given_records_inventory = []
            #  Make some people
            person_name_value = f"{uuid4()}"
            person_record, person_external_id = import_record_with_extid(
                Person,
                data={
                    "name": person_name_value
                }
            )
            given_records_inventory.append({
                "external_id": person_external_id,
                "person_record": person_record,
            })
            # and there is a spreadsheet of new identifiers to attach to them
            #
            import_sheet = []
            for person in given_records_inventory:
                import_sheet.append({
                    "PersonIdentifier.identifier": f"identifier-value-{uuid4()}",
                    "PersonIdentifier.person_identifier_type": 'popcorn',  # non-existing type
                    "PersonIdentifier.person-ext_id": person["external_id"],
                    "PersonIdentifier.ext_id": f"external-id-{uuid4()}",
                })

            csv_writer = csv.DictWriter(csv_fd, FIELDNAMES)
            csv_writer.writeheader()
            for row in import_sheet:
                csv_writer.writerow(row); csv_fd.flush()  # Make sure it's actually written to the filesystem

            # WHEN I call the data_update command pointed at the CSV
            #
            #
            call_command('bulk_add_identifiers', csv_fd.name, stdout=out)

            # THEN the people in the system should have identifiers attached to them
            #
            #
            for import_sheet_index, given_record in enumerate(given_records_inventory):
                person = given_record['person_record']
                get_record_from_external_id()
                identifier_in_system = PersonIdentifier.objects.get(person=person)
                identifier_from_import_sheet = import_sheet_index[import_sheet_index]["PersonIdentifier.identifier"]
                self.assertEqual(
                    identifier_in_system,
                    identifier_from_import_sheet,
                    msg=out.getvalue()
                )
