import csv
from django.core.management.base import BaseCommand

from bulk_data_manipulation.common import get_model_from_import_string
from core.models import PersonGrouping
from bulk.models import BulkImport

help_text = """Generate a report of all external IDs and their corresponding PKs for a given model"""


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('model', type=str, help="Model class, e.g. 'core.models.Person'")
        parser.add_argument('input_file', type=str)

    def handle(self, *args, **options):
        model = get_model_from_import_string(options['model'])
        with open(options['input_file'], 'w') as csv_fd:
            csv_writer = csv.DictWriter(csv_fd, ['external_id', 'pk'])
            csv_writer.writeheader()

            for record in model.objects.all():
                try:
                    bulk_import_record = BulkImport.objects.get(table_imported_to=model.get_db_table(),
                                                                pk_imported_to=record.pk)
                    csv_writer.writerow({
                        'external_id': bulk_import_record.pk_imported_from,
                        'pk': record.pk
                    })
                except BulkImport.DoesNotExist:
                    pass
