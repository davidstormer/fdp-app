import os
from datetime import datetime

from selenium.webdriver.common.by import By

from .models import ImportBatch
from .narwhal import do_import_from_disk, ImportReport
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4
from django.test import TestCase
from core.models import Person
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from inheritable.tests import local_test_settings_required
from unittest import expectedFailure, skip
from selenium.webdriver.support.ui import Select
import pdb

#
# class MyNonSeleniumTestCase(FunctionalTestCase):
#     """Use FunctionalTestCase as a lightweight alternative to SeleniumFunctionalTestCase when JavaScript and styling
#     do not need to be accounted for.
#     """
#
#     def test_demo_person_record(self):
#         Person.objects.create(name="Hello World")
#         people = Person.objects.all()
#         self.assertEqual(
#             1,
#             len(people)
#         )
#
#     def test_demo_login(self):
#         # Given I'm logged into the system as an Admin
#         admin_client = self.log_in(is_administrator=True)
#
#         # When I go to the root of the site '/'
#         response_admin_client = admin_client.get('/', follow=True)
#         html = response_admin_client.content
#
#         # Then I should see an h1 that reads "What are you searching for?"
#         second_h1_contents = self.get_element_text(html, 'h1', nth_element=1)
#         self.assertEqual(
#             "What are you searching for?",
#             second_h1_contents
#         )
#         # ... btw:
#         first_h1_contents = self.get_element_text(html, 'h1')
#         self.assertEqual(
#             "Full Disclosure Project",
#             first_h1_contents
#         )
#
#
# class MySeleniumTestCase(SeleniumFunctionalTestCase):
#     """Use SeleniumFunctionalTestCase to launch a selenium driven Firefox browser to test the application.
#     """
#
#     # Simple example
#     def test_demo_login_page(self):
#         self.browser.get(self.live_server_url)
#         button = self.browser.find_element_by_css_selector('button')
#         # More methods here: https://selenium-python.readthedocs.io/locating-elements.html
#         self.assertIn(
#             'Log in',
#             button.text
#         )
#
#     # But what if something fails? Comment out @expectedFailure to see!
#     @expectedFailure
#     @local_test_settings_required
#     def test_demo_broken_test(self):
#         self.browser.get(self.live_server_url)
#         self.assertIn(
#             'coo coo banana pants',
#             self.browser.page_source
#         )
#         # ... dumps a screenshot and the html output into a screendumps directory.
#
#     # And how do I log in?
#     def test_demo_logging_in(self):
#         # Given I'm logged into the system as an Admin
#         self.log_in(is_administrator=True)
#         heading = wait(self.browser.find_element_by_css_selector, 'div#content h1')
#         self.assertEqual(
#             "What are you searching for?",
#             heading.text
#         )


class TestWebUI(SeleniumFunctionalTestCase):
    def test_import_batch_page_success_scenario(self):
        # GIVEN an import has been run
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(42):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            report = do_import_from_disk('Person', csv_fd.name)

            # WHEN I go to the batch history page
            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')

            # Then I should see the basic data points
            self.assertIn('Person', self.browser.page_source)
            self.assertIn('42', self.browser.page_source)
            self.assertIn(os.path.basename(csv_fd.name), self.browser.page_source)

    @skip
    def test_import_history_success_scenario_multiple(self):
        # GIVEN several imports have been run
        for x in range(3):
            with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
                imported_records = []
                csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
                csv_writer.writeheader()
                for i in range(31 + x):
                    row = {}
                    row['name'] = f'Test Person {uuid4()}'
                    row['is_law_enforcement'] = 'checked'
                    csv_writer.writerow(row)
                    imported_records.append(row)
                csv_fd.flush()  # Make sure it's actually written to the filesystem!
                do_import_from_disk('Person', csv_fd.name)

        # WHEN I run the import_history command
        command_output = StringIO()
        time_started = datetime.now()
        call_command('narwhal_import_history', stdout=command_output)

        # THEN I should see a listing showing the number, import time, filename, model, number of records,
        # and whether it succeeded or not.
        output = command_output.getvalue()
        self.assertIn('Person', output)
        self.assertIn('31', output)
        self.assertIn('32', output)
        self.assertIn('33', output)
        self.assertIn(os.path.basename(csv_fd.name), output)

    @skip
    def test_import_history_detail_rows(self):
        # GIVEN an import has been run
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(4):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            do_import_from_disk('Person', csv_fd.name)

            # WHEN I pass the batch number as an argument to the import_history command
            command_output_stream = StringIO()
            batch_number = ImportBatch.objects.last().pk
            call_command('narwhal_import_history', batch_number, stdout=command_output_stream)

            # THEN I should see a listing showing the rows of the import
            command_output = command_output_stream.getvalue()
            for row in imported_records:
                self.assertIn(
                    row['name'],
                    command_output
                )

    def test_import_history_detail_error_rows(self):
        # GIVEN an import has been run with validation errors
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(4):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'BREAK'  # <-- bad value
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!
            do_import_from_disk('Person', csv_fd.name)

            # WHEN I go to the batch history page
            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')

            # THEN I should see a listing showing the error rows of the import
            self.assertEqual(
                4,
                self.browser.page_source.count("Enter a valid boolean value")
            )

            # And there should be no completed time
            self.assertIn(
                'Completed: Aborted',
                self.browser.find_element(By.CSS_SELECTOR, '.datum-completed').text
            )
