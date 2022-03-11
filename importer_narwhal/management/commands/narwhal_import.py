from django.core.management.base import BaseCommand
import tablib
from import_export.results import InvalidRow, Result

from ...narwhal import MODEL_ALLOW_LIST, resource_model_mapping, do_import, ImportReportRow

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
        report = do_import(options['model'], options['input_file'])

        if report.validation_errors:
            self.error("Error:")
            for row in report.validation_errors:
                self.error(row)
        if report.database_errors:
            self.error("Error:")
            for row in report.database_errors:
                self.error(row)
