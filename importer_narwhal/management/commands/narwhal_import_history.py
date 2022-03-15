from django.core.management.base import BaseCommand

from ...models import ImportBatch
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
        pass

    def handle(self, *args, **options):
        batches = ImportBatch.objects.all().order_by('-pk')
        for batch in batches:
            self.print_info(str(batch))
