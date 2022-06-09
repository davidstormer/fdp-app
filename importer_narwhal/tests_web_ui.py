import os
from datetime import datetime

from django.urls import reverse
from selenium.common.exceptions import NoSuchElementException
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
            "ERROR: 'supercalifragilisticexpialidocious' not a valid column name for Person imports",
            general_errors_div.text
        )
        self.assertNotIn(
            'there were no errors',
            self.browser.page_source
        )


class TestImportWorkflowPageElementsExist(SeleniumFunctionalTestCase):
    def test_validate_pre_validate(self):
        """Test that the CSV Preview, Info Card, and Status Guide elements are displayed on the batch detail page
        when in the pre-validate state"""
        # Given I've set up a batch from the Import batch setup page
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'mineralogize'])
            csv_writer.writeheader()
            for i in range(42):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['mineralogize'] = 'yes'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + reverse('importer_narwhal:new-batch'))
            wait(self.browser.find_element_by_css_selector, 'input#id_import_sheet') \
                .send_keys(csv_fd.name)
            Select(self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name')) \
                .select_by_visible_text('ContentPersonAllegation')

            # When I submit the setup form
            self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name').submit()

            # Then I should see a CSV Preview with the first few lines from my CSV
            csv_preview_element = wait(self.browser.find_element, By.CSS_SELECTOR, 'div.importer-csv-preview')
            self.assertIn(
                'mineralogize',
                csv_preview_element.text
            )
            self.assertIn(
                os.path.basename(csv_fd.name),
                csv_preview_element.text
            )

            # and the Info Card with details of my submission
            info_card_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-info-card')
            self.assertIn(
                os.path.basename(csv_fd.name),
                info_card_element.text
            )
            self.assertIn(
                str(len(imported_records)),
                info_card_element.text
            )
            self.assertIn(
                'ContentPersonAllegation',
                info_card_element.text
            )

            # and the Status Guide should say that the batch is loaded and ready to validate, with a 'Validate' button
            status_guide_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-status-guide')
            self.assertIn(
                'Your batch has been set up. Now it needs to be validated.',
                status_guide_element.text
            )

            status_guide_element.find_element(By.CSS_SELECTOR, 'input[value="Validate Batch"]')

            # And I should not see the errors section
            with self.subTest(msg="No errors section"):
                with self.assertRaises(NoSuchElementException):
                    self.browser.find_element(By.CSS_SELECTOR, 'div.importer-errors')

            # And I should not see the rows section
            with self.subTest(msg="No imported rows section"):
                with self.assertRaises(NoSuchElementException):
                    self.browser.find_element(By.CSS_SELECTOR, 'div.importer-imported-rows')

    def test_validate_post_validate_errors(self):
        """Test that the Info Card, Status Guide, General Errors Readout, Error Rows, and Error Rows Paginator
        elements are displayed on the batch detail page when in the post-validate-errors state"""

        # Given I've set up a batch from the Import batch setup page containing an erroneous column, and cell
        # validation errors totalling over 100
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement', 'not_a_legit_column_name'])
            csv_writer.writeheader()
            for i in range(150):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'BREAK'  # <-- bad value
                row['not_a_legit_column_name'] = "too legit to quit"
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + reverse('importer_narwhal:new-batch'))
            wait(self.browser.find_element_by_css_selector, 'input#id_import_sheet') \
                .send_keys(csv_fd.name)
            Select(self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name')) \
                .select_by_visible_text('Person')
            self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name').submit()

        # When I run the validation step
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Validate Batch"]') \
            .click()

        with self.subTest(msg="Info Card"):
            # Then I should see the Info Card with details of my submission
            info_card_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-info-card')
            self.assertIn(
                os.path.basename(csv_fd.name),
                info_card_element.text
            )
            self.assertIn(
                str(len(imported_records)),
                info_card_element.text
            )
            self.assertIn(
                'Person',
                info_card_element.text
            )

        with self.subTest(msg="Status Guide"):
            # Then I should see the Status Guide
            status_guide_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-status-guide')
            self.assertIn(
                'Errors encountered during validation. Please correct errors and start a new batch.',
                status_guide_element.text
            )
            status_guide_element.find_element(By.LINK_TEXT, 'Start Over')

        # Then I should see an errors section
        errors_section = wait(self.browser.find_element_by_css_selector, 'div.importer-errors')
        with self.subTest(msg="General Errors Readout"):
            # and it should contain an error about the erroneous column
            self.assertIn(
                "ERROR: 'not_a_legit_column_name' not a valid column name for Person imports",
                errors_section.text
            )
        with self.subTest(msg="Error Rows"):
            # and it should contain 100 row level errors (limited by pagination)
            self.assertEqual(
                100,
                errors_section.text.count("Enter a valid boolean value")
            )
            # and the row level errors paginator
            self.browser.find_element(By.CSS_SELECTOR, 'nav[aria-label="Pagination"]')

        # And I should not see the imported rows section
        with self.subTest(msg="No imported rows section"):
            with self.assertRaises(NoSuchElementException):
                self.browser.find_element(By.CSS_SELECTOR, 'div.importer-imported-rows')
