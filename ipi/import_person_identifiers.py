import csv
from core.models import PersonIdentifier
from supporting.models import PersonIdentifierType
from bulk.models import BulkImport
from django.core.exceptions import MultipleObjectsReturned
from django.db.utils import IntegrityError
from django.db import transaction
import logging

REQUIRED_FIELDS = [
    'PersonIdentifier.id__external',
    'PersonIdentifier.identifier',
    'PersonIdentifier.id__external'
]


class ImportErrors(Exception):
    pass


class RequiredFieldMissing(Exception):
    pass


class PersonIdentifierTypeMissing(Exception):
    pass


class PersonMissing(Exception):
    pass


class NoNaturalBooleanValueFound(Exception):
    pass


def parse_natural_boolean_string(value: str or bool or None) -> bool or None:
    """Interpret various spreadsheet indications of 'True' and 'False'.
    Balks if a clear interpretation can't be made.
    Quietly interprets a blank value '' as empty and returns None.
    """
    if value is None:
        return None
    if value is False:
        return False
    if value is True:
        return True

    value = value.lower()
    if value == 'true' or \
            value == 'checked' or \
            value == '1':
        return True
    elif value == 'false' or \
            value == 'unchecked' or \
            value == '0':
        return False
    elif value == '' or \
            value == 'null' or \
            value == 'none':
        return None
    else:
        raise NoNaturalBooleanValueFound


def main_loop(csv_reader):
    errors_count = 0
    for i, row in enumerate(csv_reader):
        try:
            if i == 0:
                for required_field in REQUIRED_FIELDS:
                    try:
                        row[required_field]
                    except KeyError:
                        raise RequiredFieldMissing(f"Row {i + 1}: Required '{required_field}' column "
                                                   f"missing from import sheet.")

            # Get Person pk from PersonIdentifier.person column or
            # 'external' PersonIdentifier.person__external id
            person_id = None
            if row['PersonIdentifier.person__external']:
                try:
                    bulk_import_record = BulkImport.objects.get(
                        pk_imported_from=row['PersonIdentifier.person__external'])
                    person_id = bulk_import_record.pk_imported_to
                except BulkImport.DoesNotExist as e:
                    print(f"Couldn't find Person by external id: '{row['PersonIdentifier.person__external']}'")
                    raise e
                except MultipleObjectsReturned as e:
                    print(
                        f"Multiple Person records found by external id: "
                        f"'{row['PersonIdentifier.person__external']}'")
                    raise e
            else:
                person_id = row['PersonIdentifier.person']
            if not person_id:
                raise PersonMissing("Couldn't find Person pk or external id")

            # Lookup or create PersonIdentifierType (dependency)
            if row.get('PersonIdentifier.person_identifier_type', False):
                identifier_type, created = PersonIdentifierType.objects.get_or_create(
                    name=row['PersonIdentifier.person_identifier_type'])
                if created:
                    print(f"Row: {i + 1} Created PersonIdentifierType: {identifier_type}")
            else:
                raise PersonIdentifierTypeMissing(
                    "Add 'PersonIdentifier.person_identifier_type' column to import sheet")

            # Create PersonIdentifier
            try:
                new_pid = PersonIdentifier()
                new_pid.person_id = person_id
                new_pid.identifier = row['PersonIdentifier.identifier']
                new_pid.person_identifier_type_id = identifier_type.pk
                new_pid.description = row.get('PersonIdentifier.description', '')
                new_pid.end_day = row.get('PersonIdentifier.end_day', 0)
                new_pid.end_month = row.get('PersonIdentifier.end_month', 0)
                new_pid.end_year = row.get('PersonIdentifier.end_year', 0)
                new_pid.start_day = row.get('PersonIdentifier.start_day', 0)
                new_pid.start_month = row.get('PersonIdentifier.start_month', 0)
                new_pid.start_year = row.get('PersonIdentifier.start_year', 0)
                new_pid.as_of = parse_natural_boolean_string(row.get('PersonIdentifier.as_of', False))
                new_pid.save()

                BulkImport.objects.create(
                    pk_imported_from=row['PersonIdentifier.id__external'],
                    pk_imported_to=new_pid.pk,
                    table_imported_to=PersonIdentifier.get_db_table(),
                    data_imported=''
                )
                print(f"Row: {i + 1} Imported PersonIdentifier: {new_pid}")
            except IntegrityError as e:
                print(f"Row: {i + 1} Integrity error, skipping {row} -- {e}")
                raise e
        except Exception as e:  # Catch all errors until the end
            errors_count += 1
            logging.error(e)
            # raise e  # Uncomment for debugging
            continue
    return errors_count


def import_person_identifiers(csv_reader: csv.DictReader, force_mode: bool = False) -> int:
    """Import PersonIdentifier records from a CsvReader or other iterable data structure like a dictionary.
    Expects Wholesale importer standard template CSV field names.
    """

    # Force mode: import as much as you can, even though errors are encountered.
    if force_mode is True:
        errors_count = main_loop(csv_reader)
        return errors_count

    # Default, Rollback mode: rollback import if errors are encountered, don't save anything.
    else:
        try:
            # If any errors are encountered, rollback the whole import as a single atomic transaction
            with transaction.atomic():
                errors_count = main_loop(csv_reader)
                if errors_count > 0:
                    raise ImportErrors  # If any errors, raise an exception to cancel the atomic transaction
        except ImportErrors:  # Catch the import errors exception, after transaction was cancelled, so we
            # can return the error count
            return errors_count
        return errors_count
