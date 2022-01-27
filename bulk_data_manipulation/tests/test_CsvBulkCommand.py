import tempfile
from csv import DictWriter
from io import StringIO

from django.core.management import call_command

from bulk_data_manipulation.common import CsvBulkCommand
from django.test import SimpleTestCase


class CsvBulkCommandTestCase(SimpleTestCase):
    # 1: GIVEN I subclass CsvBulkCommand to make a new management command

    class MyBulkCommand(CsvBulkCommand):

        def handle(self, *args, **options):

            # 2: and given I provide a callback function that notes each record was passed to it
            def callback(row, **kwargs):
                # 5: THEN the callback function should see each row of the CSV file
                print(row)
                print(kwargs)

    # 3: and given I have a CSV file of records to act on
    csv_data = [
        {
            'id': 0,
            'field1': 'confident',
        },
        {
            'id': 1,
            'field1': 'middlingness',
        },
        {
            'id': 2,
            'field1': 'bedunch',
        }
    ]
    with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
        csv_writer = DictWriter(csv_fd, ['id', 'field1'])
        for record in csv_data:
            csv_writer.writerow(record); csv_fd.flush()  # <- ACTUALLY WRITE TO DISK

    # 4: WHEN I call the new command on the CSV file
    command_output = StringIO()
    call_command('bulk_delete', 'core.models.Person', csv_fd.name, stdout=command_output)


    # TODO: def test_empty_file(self):
