from core.models import PersonIdentifier
import csv
from django.core.management.base import BaseCommand

help_text = """Generate an export of PersonIdentifiers to a csv file"""


def get_record_data(record) -> dict:
    record_data = {}
    # RE: '._meta' c.f. https://stackoverflow.com/a/3647936
    for field in record.__class__._meta.fields + record.__class__._meta.many_to_many:
        record_data[field.name] = str(getattr(record, field.name))
    return record_data


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('output_file', type=str)

    def handle(self, *args, **options):
        person_identifiers = PersonIdentifier.objects.all().select_related('person')
        column_names = list(get_record_data(person_identifiers[0]).keys())
        column_names.append('person.pk')

        with open(options['output_file'], 'w') as output_file_fd:
            csv_writer = csv.DictWriter(output_file_fd, column_names)
            csv_writer.writeheader()
            for person_identifier in person_identifiers:
                row = get_record_data(person_identifier)
                row['person.pk'] = person_identifier.person.pk
                csv_writer.writerow(row)
