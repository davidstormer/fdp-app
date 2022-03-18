from django.core.management.base import BaseCommand

from ...models import ImportBatch
from ...narwhal import delete_batch, BatchDeleteFailed

help_text = """Delete records created by an import"""


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
        parser.add_argument('batch_number')

    def handle(self, *args, **options):
        batch = ImportBatch.objects.get(pk=options['batch_number'])
        self.print_info(
            f"""Batch number: {batch.pk}
Start time: {batch.start_time:%Y-%m-%d %H:%M:%S}
File name: {batch.submitted_file_name}
Model name: {batch.target_model_name}
Rows: {batch.number_of_rows}
Errors: {'Errors encountered' if batch.errors_encountered else 'No errors'}"""
        )
        batch_number_confirmation = input("Are you sure you want to delete these records? "
                                          "Enter the batch number to confirm:")
        if str(options['batch_number']) == str(batch_number_confirmation):
            try:
                delete_batch(options['batch_number'])
            except BatchDeleteFailed:
                self.print_error("Updates found in batch. Cannot delete. Quiting.")
        else:
            self.print_error("Numbers don't match. Quiting.")
