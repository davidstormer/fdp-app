from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Model
from bulk.models import BulkImport
from core.models import Grouping
from supporting.models import County
import csv
from bulk_data_manipulation.common import get_record_from_external_id, ImportErrors
from uuid import uuid4
import pdb

FIELDNAMES = ["Grouping.external_id", "Grouping.name", "Grouping.belongs_to_grouping_extid",
              "Grouping.counties_extid_cdv"]

help_text = f"""This tool updates group data. Takes a CSV file with the following fields: {FIELDNAMES} and updates 
the given records.
"""


def parse_comma_delimited_values(input_value: str) -> list:
    output_values = input_value.split(',')
    for i, value in enumerate(output_values):
        output_values[i] = value.strip()
    return output_values


def get_records_from_extid_cdv(model: object, input_value: str) -> list:
    """Take a comma delimited list of external IDs and return a list of those records.
    """
    if input_value:
        records = []
        extids = parse_comma_delimited_values(input_value)
        for county_extid in extids:
            record = get_record_from_external_id(model, county_extid)
            records.append(record)
        return records
    else:
        return []


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        # TODO: Remove this notice, when we're ready to roll
        self.stdout.write(self.style.WARNING(
            "Under construction! Don't use this"
        ))
        try:
            with open(options['csv_file'], 'r') as csv_fd:
                csv_reader = csv.DictReader(csv_fd)
                errors_count = 0
                with transaction.atomic():  # Start an atomic transaction
                    for row in csv_reader:
                        try:
                            grouping = get_record_from_external_id(Grouping, row["Grouping.external_id"])
                            grouping.name = row["Grouping.name"]
                            grouping.belongs_to_grouping = \
                                get_record_from_external_id(Grouping, row["Grouping.belongs_to_grouping_extid"])
                            grouping.save()
                            counties = get_records_from_extid_cdv(County, row["Grouping.counties_extid_cdv"])
                            grouping.counties.set(counties)
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
