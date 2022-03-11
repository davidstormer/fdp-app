from django.core.management.base import BaseCommand
import tablib

from ...narwhal import MODEL_ALLOW_LIST, resource_model_mapping

help_text = """UNDER CONSTRUCTION Import data into the system"""


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('model', choices=MODEL_ALLOW_LIST, help="Model class, e.g. 'Person'")
        parser.add_argument('input_file')

    def handle(self, *args, **options):

        with open(options['input_file'], 'r') as fd:
            input_sheet = tablib.Dataset().load(fd)
            resource_class = resource_model_mapping['Person']
            resource = resource_class()
            result = resource.import_data(input_sheet, dry_run=False)
