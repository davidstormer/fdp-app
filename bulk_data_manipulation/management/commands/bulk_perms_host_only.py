from django.core.management.base import BaseCommand
from bulk_data_manipulation.common import get_model_from_import_string, CsvBulkCommand, get_record_from_external_id, \
    parse_natural_boolean_string
import os
from django.db.models import Model

help_text = """Set for_host_only on imported records based on external ID. Updates either small set given as positional 
arguments on the commandline or takes a csv file full of ids."""


class Command(CsvBulkCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('model', type=str, help="Model class, e.g. 'core.models.Person'")
        parser.add_argument('input_file', type=str)

    def handle(self, *args, **options):
        if os.stat(options['input_file']).st_size < 1:
            self.stdout.write(self.style.ERROR(f"WARNING! {options['input_file']} is an empty file. Doing nothing. "
                                               f"Quitting..."))
        model = get_model_from_import_string(options['model'])

        def callback_func(model: Model, row: dict) -> None:
            """This function takes a row from the main loop in csv_bulk_action and processes it."""
            record = get_record_from_external_id(model, row["id__external"])
            record.for_host_only = parse_natural_boolean_string(row["for_host_only"])
            record.save()

        self.csv_bulk_action(options, callback_func=callback_func)
