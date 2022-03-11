from django.core.management.base import BaseCommand
import tablib

from ...narwhal import MODEL_ALLOW_LIST, resource_model_mapping, do_import

help_text = """UNDER CONSTRUCTION Import data into the system"""


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('model', choices=MODEL_ALLOW_LIST, help="Model class, e.g. 'Person'")
        parser.add_argument('input_file')

    def handle(self, *args, **options):
        result = do_import(options['input_file'])
        if result.has_validation_errors():
            self.stdout.write(self.style.ERROR(
                'Error'
            ))
