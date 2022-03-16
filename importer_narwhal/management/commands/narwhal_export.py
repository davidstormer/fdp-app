from django.core.management.base import BaseCommand

from ...narwhal_export import do_export

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
        parser.add_argument('model_name')
        parser.add_argument('output_file')

    def handle(self, *args, **options):
        do_export(options['model_name'], options['output_file'])
