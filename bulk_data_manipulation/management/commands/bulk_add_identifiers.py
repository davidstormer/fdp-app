"""UNDER CONSTRUCTION!!! Don't use this
For a working version check out: https://github.com/Full-Disclosure-Project/fdp-app/blob/FDAB-13-import_person_ids/ipi/import_person_identifiers.py
"""

from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from core.models import Person
from core.models import PersonIdentifier
from supporting.models import PersonIdentifierType
import csv
from bulk_data_manipulation.common import get_record_from_external_id, ImportErrors, ExternalIdMissing, \
    import_record_with_extid
import pdb
import os


FIELDNAMES = ["PersonIdentifier.identifier", "PersonIdentifier.person_identifier_type",
              "PersonIdentifier.person-ext_id", "PersonIdentifier.ext_id"]

help_text = f"""This tool adds new person identifiers. Takes a CSV file with the following fields: {FIELDNAMES} and 
creates the given records. If the person identifier type doesn't exist already (by name) it will create a new one 
automatically. If any errors are encountered rolls back transaction.
"""


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        # TODO: Remove this notice, when we're ready to roll
        self.stdout.write(self.style.WARNING(
            "Under construction! Don't use this"
        ))
        if os.stat(options['csv_file']).st_size < 1:
            self.stdout.write(self.style.ERROR(f"WARNING! {options['input_file']} is an empty file. Doing nothing. "
                                               f"Quitting..."))

        try:
            with open(options['csv_file'], 'r') as csv_fd:
                csv_reader = csv.DictReader(csv_fd)
                errors_count = 0
                with transaction.atomic():  # Start an atomic transaction
                    for row in csv_reader:
                        try:
                            # Get person
                            person = get_record_from_external_id(Person, row["PersonIdentifier.person-ext_id"])
                            # Get or make identifier type
                            try:
                                person_identifier_type = PersonIdentifier.objects.get(
                                    name=row["PersonIdentifier.person_identifier_type"])
                            except PersonIdentifier.DoesNotExist:
                                person_identifier_type = PersonIdentifier.objects.create(
                                    name=row["PersonIdentifier.person_identifier_type"])
                            # Make sure PersonIdentifier external id isn't already in the system
                            try:
                                get_record_from_external_id(PersonIdentifier, row['PersonIdentifier.ext_id'])
                                raise Exception(f"External identifier already exists: {row['PersonIdentifier.ext_id']}")
                            except ExternalIdMissing:
                                pass
                            # Import the record
                            import_record_with_extid(
                                model=PersonIdentifier,
                                external_id=row['PersonIdentifier.ext_id'],
                                data={
                                    "person": person,
                                    "identifier": row['PersonIdentifier.identifier'],
                                    "person_identifier_type": person_identifier_type,
                                }
                            )
                        except Exception as e:
                            errors_count += 1
                            self.stdout.write(self.style.ERROR(
                                f"Row:{csv_reader.line_num} : {e}"
                            ))
                    if errors_count > 0:
                        self.stdout.write(self.style.ERROR("Errors encountered! Undoing..."))
                        raise ImportErrors  # If any errors, raise an exception which rolls back the atomic transaction
        except FileNotFoundError as e:
            self.stdout.write(self.style.ERROR(f"Couldn't find file {options['csv_file']}. Quitting..."))
        except ImportErrors as e:
            self.stdout.write(self.style.ERROR(f"Import encountered errors. Quiting..."))
