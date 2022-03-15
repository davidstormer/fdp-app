from timeit import timeit
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4
from core.models import Person


class NarwhalPerformanceTests(TestCase):
    # This test takes about a half hour to run, so it's disabled by default
    # To run it, use the --pattern flag on the test runner:
    # `python manage.py test --settings=fdp.configuration.test.test_local_settings --pattern 'performance*'`
    def test_performance_test_100k(self):
        # GIVEN there is an input csv of one hundred thousand records
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(1000 * 100):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # WHEN I run the import from the management command
            command_output = StringIO()

            def call_import():
                call_command('narwhal_import', 'Person', csv_fd.name, stdout=command_output)

            run_time = timeit(call_import, number=1)

            # Then the import should succeed within 60 minutes
            print(f"run_time: {run_time}")
            self.assertLessEqual(
                run_time,
                60 * 60,
                msg="100K import run took longer than sixty minutes!"
            )
            # THEN the records should be added to the system
            self.assertEqual(
                10 * 10000,
                Person.objects.all().count()
            )
