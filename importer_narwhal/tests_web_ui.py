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
from django.test import TestCase, override_settings
from core.models import Person
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from inheritable.tests import local_test_settings_required
from unittest import expectedFailure, skip
from selenium.webdriver.support.ui import Select
import pdb

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

    def test_import_batch_page_errors_pagination_first_page(self):
        # GIVEN an import has been run with validation errors
        with tempfile.NamedTemporaryFile(mode='w') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(300):
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
                100,
                self.browser.page_source.count("Enter a valid boolean value")
            )

    def test_batch_listing(self):
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

            # WHEN I go to the batch listing page
            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + f'/changing/importer')

            # Then I should see the batch in the listing
            self.assertIn('Person', self.browser.page_source)
            self.assertIn('42', self.browser.page_source)
            self.assertIn(os.path.basename(csv_fd.name), self.browser.page_source)

    def test_batch_listing_links_to_detail_page(self):
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

            # WHEN I click one of the batches on the batch listing page
            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + f'/changing/importer')
            self.browser.find_element(By.CSS_SELECTOR, '.row-1 a').click()

            # Then I should see the batch detail page
            self.assertIn('Person', self.browser.page_source)
            self.assertIn('42', self.browser.page_source)
            self.assertIn(os.path.basename(csv_fd.name), self.browser.page_source)

    def test_validation_step_column_mapping_errors(self):
        # Given I upload an import sheet with a nonsense column that doesn't match any of the columns of the resource
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'supercalifragilisticexpialidocious'])
            csv_writer.writeheader()
            for i in range(42):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['supercalifragilisticexpialidocious'] = 'yes'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + f'/changing/importer/batch/new')
            wait(self.browser.find_element_by_css_selector, 'input#id_import_sheet') \
                .send_keys(csv_fd.name)
            Select(self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name')) \
                .select_by_visible_text('Person')

            # And I'm on the validation step of running an import
            self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name').submit()

        # When I click Validate Batch
        wait(self.browser.find_element_by_css_selector, 'input[value="Validate Batch"]') \
            .submit()

        # Then I should see an error report that warns me that it's an un-expected field name
        general_errors_div = wait(self.browser.find_element_by_css_selector, 'div.general-errors')
        self.assertIn(
            'WARNING: supercalifragilisticexpialidocious not a valid column name for Person imports',
            general_errors_div.text
        )
        self.assertNotIn(
            'there were no errors',
            self.browser.page_source
        )
