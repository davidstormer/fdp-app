from django.core.management.base import BaseCommand

from ...models import ImportBatch

help_text = """Display history of imports"""


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
        parser.add_argument('batch_number', type=int, nargs='?')

    def handle(self, *args, **options):
        if options['batch_number']:
            batch = ImportBatch.objects.get(pk=options['batch_number'])
            self.print_info(
                f"""Batch number: {batch.pk}
Started: {batch.started_fmt}
Completed: {batch.completed_fmt}
File name: {batch.submitted_file_name}
Model name: {batch.target_model_name}
Rows: {batch.number_of_rows}
Errors: {'Errors encountered' if batch.errors_encountered else 'No errors'}"""
            )
            for row in batch.imported_rows.all():
                self.print_info(str(row))
            for row in batch.error_rows.all():
                self.print_info(str(row))

        else:
            batches = ImportBatch.objects.all().order_by('-pk')
            for batch in batches:
                self.print_info(str(batch))
