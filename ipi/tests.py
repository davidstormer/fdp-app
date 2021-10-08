import pdb

from django.test import LiveServerTestCase, SimpleTestCase, TransactionTestCase
from .import_person_identifiers import import_person_identifiers, parse_natural_boolean_string, \
    NoNaturalBooleanValueFound
from core.models import Person, PersonIdentifier
from supporting.models import PersonIdentifierType
from bulk.models import BulkImport
from faker import Faker
from pprint import pprint
import logging
import csv
import json

faker = Faker()


def csv_to_list_dict(csv_reader):
    """Utility for making test data structures for inserting into tests
    """
    data = []
    for i, row in enumerate(csv_reader):
        data.append(row)
    pprint(data)


def generate_test_person(external_id: str) -> Person or None:
    try:
        BulkImport.objects.get(pk_imported_from=external_id)
        logging.warning(f"Person with external id {external_id} already exists. Skipping!")
        return None
    except BulkImport.DoesNotExist as e:
        person = Person.objects.create(name=faker.name())
        BulkImport.objects.create(
            pk_imported_to=person.pk,
            pk_imported_from=external_id,
            table_imported_to=Person.get_db_table(),
            data_imported=''
        )
        return person


def make_fake_people(csv_file_name):
    with open(csv_file_name, 'r') as f:
        csv_reader = csv.DictReader(f)
        for person in csv_reader:
            generate_test_person(person['PersonIdentifier.person__external'])


class DatabaseTransactions(TransactionTestCase):
    def test_rollback_on_error(self):
        csv_reader = [
            # Good
            {'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '1',
             'PersonIdentifier.identifier': '1',
             'PersonIdentifier.person__external': 'ext-id-1',  # Does exist
             'PersonIdentifier.person_identifier_type': 'Type1',
             },
            # BAD
            {'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '2',
             'PersonIdentifier.identifier': '2',
             'PersonIdentifier.person__external': 'ext-id-2',  # Reference a Person record that doesn't exist
             'PersonIdentifier.person_identifier_type': 'Type2',
             },
            # Good
            {'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '3',
             'PersonIdentifier.identifier': '3',
             'PersonIdentifier.person__external': 'ext-id-1',  # Does exist
             'PersonIdentifier.person_identifier_type': 'Type3',
             },
            # BAD
            {'PersonIdentifier.end_year': 'NOT A NUMBER',  # Bad value
             'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '4',
             'PersonIdentifier.identifier': '4',
             'PersonIdentifier.person__external': 'ext-id-1',  # Does exist
             'PersonIdentifier.person_identifier_type': 'Type4',
             },
        ]

        # Take note of how many PersonIdentifier records in the system before botched import (zero)
        pids_before = PersonIdentifier.objects.all()
        self.assertEqual(0, len(pids_before))
        # And PersonIdentifierType records
        self.assertEqual(0, len(PersonIdentifierType.objects.all()))

        # Create dependency Person record
        generate_test_person('ext-id-1')

        # Run the importer
        errors_count = import_person_identifiers(csv_reader)

        # Two bad records, two errors
        self.assertEqual(errors_count, 2)

        # Because there were errors the import rolled back,
        # thus the good records proceeding the errors shouldn't be in the db either.
        # No new PersonIdentifier records in the system after failed import
        pids_after = PersonIdentifier.objects.all()
        self.assertEqual(len(pids_before), len(pids_after))

        # I shouldn't see PersonIdentifierType records either
        self.assertEqual(0, len(PersonIdentifierType.objects.all()))

    def test_force_mode(self):
        csv_reader = [
            # Good
            {'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '1',
             'PersonIdentifier.identifier': '1',
             'PersonIdentifier.person__external': 'ext-id-1',  # Does exist
             'PersonIdentifier.person_identifier_type': 'Type1',
             },
            # BAD
            {'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '2',
             'PersonIdentifier.identifier': '2',
             'PersonIdentifier.person__external': 'ext-id-2',  # Reference a Person record that doesn't exist
             'PersonIdentifier.person_identifier_type': 'Type2',
             },
            # BAD
            {'PersonIdentifier.end_year': 'NOT A NUMBER',  # Bad value
             'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '4',
             'PersonIdentifier.identifier': '4',
             'PersonIdentifier.person__external': 'ext-id-1',  # Does exist
             'PersonIdentifier.person_identifier_type': 'Type4',
             },
            # Good
            {'PersonIdentifier.description': '',
             'PersonIdentifier.id__external': '3',
             'PersonIdentifier.identifier': '3',
             'PersonIdentifier.person__external': 'ext-id-1',  # Does exist
             'PersonIdentifier.person_identifier_type': 'Type3',
             },
        ]

        # Take note of how many PersonIdentifier records in the system before botched import (zero)
        pids_before = PersonIdentifier.objects.all()
        self.assertEqual(0, len(pids_before))

        # Create dependency Person record
        generate_test_person('ext-id-1')

        # Run the importer, in FORCE MODE
        errors_count = import_person_identifiers(csv_reader, force_mode=True)

        # Two bad records, two errors
        self.assertEqual(errors_count, 2)

        # Even though there were errors the import should have saved what records imported successfully
        # Two good records, two saved in the db
        pids_after = PersonIdentifier.objects.all()
        self.assertEqual(2, len(pids_after))

        # I should see three dependency PersonIdentifierType records too
        # Fourth one is missing because the system choked on the bad field contents before creating it
        self.assertEqual(3, len(PersonIdentifierType.objects.all()))


class ImportPersonIdentifierTestCase(LiveServerTestCase):

    def test_generate_test_person_skip_ext_id_dupes(self):
        self.assertEqual(type(generate_test_person('same_id')), type(Person()))
        self.assertEqual(type(generate_test_person('same_id')), type(None))

    def test_run_importer(self):
        csv_reader = [{'PersonIdentifier.as_of': 'TRUE',
                       'PersonIdentifier.description': 'Description field here',
                       'PersonIdentifier.end_day': '1',
                       'PersonIdentifier.end_month': '1',
                       'PersonIdentifier.end_year': '1999',
                       'PersonIdentifier.id__external': 'pid-48380-1',
                       'PersonIdentifier.identifier': '1633548380',
                       'PersonIdentifier.person__external': 'ext-id-1',
                       'PersonIdentifier.person_identifier_type': 'Type1',
                       'PersonIdentifier.start_day': '1',
                       'PersonIdentifier.start_month': '1',
                       'PersonIdentifier.start_year': '1998'},
                      {'PersonIdentifier.as_of': 'FALSE',
                       'PersonIdentifier.description': 'Description field here',
                       'PersonIdentifier.end_day': '1',
                       'PersonIdentifier.end_month': '1',
                       'PersonIdentifier.end_year': '1999',
                       'PersonIdentifier.id__external': 'pid-48380-2',
                       'PersonIdentifier.identifier': '1633548707',
                       'PersonIdentifier.person__external': 'ext-id-1',
                       'PersonIdentifier.person_identifier_type': 'Type1',
                       'PersonIdentifier.start_day': '1',
                       'PersonIdentifier.start_month': '1',
                       'PersonIdentifier.start_year': '1998'},
                      {'PersonIdentifier.as_of': 'FALSE',
                       'PersonIdentifier.description': 'Description field here',
                       'PersonIdentifier.end_day': '1',
                       'PersonIdentifier.end_month': '1',
                       'PersonIdentifier.end_year': '1999',
                       'PersonIdentifier.id__external': 'pid-48380-3',
                       'PersonIdentifier.identifier': '1633548715',
                       'PersonIdentifier.person__external': 'ext-id-2',
                       'PersonIdentifier.person_identifier_type': 'Type2',
                       'PersonIdentifier.start_day': '1',
                       'PersonIdentifier.start_month': '1',
                       'PersonIdentifier.start_year': '1998'},
                      {'PersonIdentifier.as_of': 'FALSE',
                       'PersonIdentifier.description': 'Description field here',
                       'PersonIdentifier.end_day': '1',
                       'PersonIdentifier.end_month': '1',
                       'PersonIdentifier.end_year': '1999',
                       'PersonIdentifier.id__external': 'pid-48380-4',
                       'PersonIdentifier.identifier': '1633548720',
                       'PersonIdentifier.person__external': 'ext-id-2',
                       'PersonIdentifier.person_identifier_type': 'Type2',
                       'PersonIdentifier.start_day': '1',
                       'PersonIdentifier.start_month': '1',
                       'PersonIdentifier.start_year': '1998'},
                      {'PersonIdentifier.as_of': 'FALSE',
                       'PersonIdentifier.description': 'Description field here',
                       'PersonIdentifier.end_day': '1',
                       'PersonIdentifier.end_month': '1',
                       'PersonIdentifier.end_year': '1999',
                       'PersonIdentifier.id__external': 'pid-48380-5',
                       'PersonIdentifier.identifier': '1633548727',
                       'PersonIdentifier.person__external': 'ext-id-0',
                       'PersonIdentifier.person_identifier_type': 'Type3',
                       'PersonIdentifier.start_day': '1',
                       'PersonIdentifier.start_month': '1',
                       'PersonIdentifier.start_year': '1998'}]

        # Add an existing PersonIdentifierType
        PersonIdentifierType.objects.create(name='Type1')

        # Create requisite Person records
        test_person_external_ids = [
            'ext-id-0',
            'ext-id-1',
            'ext-id-2',
        ]
        for test_person_external_id in test_person_external_ids:
            generate_test_person(test_person_external_id)

        # Run the importer
        import_person_identifiers(csv_reader)

        # Assert that the data imported successfully
        for csv_row in csv_reader:
            resulting_import_record = BulkImport.objects.get(
                table_imported_to=PersonIdentifier.get_db_table(),
                pk_imported_from=csv_row['PersonIdentifier.id__external']
            )
            imported_person_identifier = PersonIdentifier.objects.get(
                pk=resulting_import_record.pk_imported_to
            )
            self.assertEqual(imported_person_identifier.identifier, csv_row['PersonIdentifier.identifier'])
            self.assertEqual(str(imported_person_identifier.start_month), csv_row['PersonIdentifier.start_month'])
            self.assertEqual(str(imported_person_identifier.start_day), csv_row['PersonIdentifier.start_day'])
            self.assertEqual(str(imported_person_identifier.start_year), csv_row['PersonIdentifier.start_year'])
            self.assertEqual(str(imported_person_identifier.end_year), csv_row['PersonIdentifier.end_year'])

    def import_md_data_set(self):
        """One-off test case. To run, add test_ to the beginning of the function name."""
        # Generate requisite fake people to link to
        make_fake_people('People_Identifiers_bulk_import.csv')

        # Import the person identifiers
        with open('People_Identifiers_bulk_import.csv', 'r') as f:
            csv_reader = csv.DictReader(f)
            import_person_identifiers(csv_reader)

        print(self.live_server_url)
        # pdb.set_trace()


class HelperFunctionsTests(SimpleTestCase):
    def test_natural_boolean(self):
        self.assertEqual(parse_natural_boolean_string('True'), True)
        self.assertEqual(parse_natural_boolean_string('TRUE'), True)
        self.assertEqual(parse_natural_boolean_string(True), True)
        self.assertEqual(parse_natural_boolean_string('checked'), True)
        self.assertEqual(parse_natural_boolean_string('1'), True)
        self.assertEqual(parse_natural_boolean_string(''), None)
        self.assertEqual(parse_natural_boolean_string('None'), None)
        self.assertEqual(parse_natural_boolean_string(None), None)
        self.assertEqual(parse_natural_boolean_string('False'), False)
        self.assertEqual(parse_natural_boolean_string('FALSE'), False)
        self.assertEqual(parse_natural_boolean_string(False), False)
        self.assertEqual(parse_natural_boolean_string('0'), False)
        self.assertEqual(parse_natural_boolean_string('unchecked'), False)
        self.assertRaises(NoNaturalBooleanValueFound, parse_natural_boolean_string, 'Verily verily!')
