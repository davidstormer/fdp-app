from django.core.management.base import BaseCommand
from ...narwhal import MODEL_ALLOW_LIST, do_import

help_text = """Import data into the system"""


class Command(BaseCommand):
    help = help_text

    def print_error(self, message):
        self.stdout.write(self.style.ERROR(
            message
        ))

    def print_info(self, message):
        self.stdout.write(
            message
        )

    def add_arguments(self, parser):
        parser.add_argument('model', choices=MODEL_ALLOW_LIST, help="Model class, e.g. 'Person'")
        parser.add_argument('input_file')

    def handle(self, *args, **options):
        report = do_import(options['model'], options['input_file'])

        if report.imported_records:
            for row in report.imported_records:
                self.print_info(str(row))
        else:
            self.print_error("NO RECORDS IMPORTED")
        if report.validation_errors:
            self.print_error("Error:")
            for row in report.validation_errors:
                self.print_error(str(row))
        if report.database_errors:
            self.print_error("Error:")
            for row in report.database_errors:
                self.print_error(str(row))

    def get_version(self):
        return '1653407733'
