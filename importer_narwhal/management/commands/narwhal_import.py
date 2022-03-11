from django.core.management.base import BaseCommand
import tablib
from import_export.results import InvalidRow, Result

from ...narwhal import MODEL_ALLOW_LIST, resource_model_mapping, do_import

help_text = """UNDER CONSTRUCTION Import data into the system"""


class Command(BaseCommand):
    help = help_text

    def error(self, message):
        self.stdout.write(self.style.ERROR(
            message
        ))

    def add_arguments(self, parser):
        parser.add_argument('model', choices=MODEL_ALLOW_LIST, help="Model class, e.g. 'Person'")
        parser.add_argument('input_file')

    def handle(self, *args, **options):
        result = do_import(options['model'], options['input_file'])
        if result.has_validation_errors():
            for invalid_row in result.invalid_rows:
                self.error(f"{invalid_row.number} | {invalid_row.error_dict} | {invalid_row.values}")
        if result.has_errors():
            for error_row in result.row_errors():
                row_num = error_row[0]
                errors = error_row[1]
                for error in errors:
                    self.error(f"{row_num} | {error.error} | {dict(error.row)}")
