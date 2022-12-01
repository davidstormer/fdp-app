import os
from datetime import datetime, timedelta
from time import sleep
from unittest.mock import patch

import dateparser
from django.db import models
from django.urls import reverse
from django.utils import timezone
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from .models import ImportBatch, MODEL_ALLOW_LIST, ExportBatch
from .narwhal import do_import_from_disk, ImportReport, do_export
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import tempfile
import csv
from uuid import uuid4
from django.test import TestCase, override_settings, tag
from core.models import Person
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from inheritable.tests import local_test_settings_required
from unittest import expectedFailure, skip
from selenium.webdriver.support.ui import Select

import pdb


def wait_until_dry_run_is_done():
    for _ in range(60):
        if ImportBatch.objects.last().dry_run_completed:
            break
        else:
            sleep(1)


def wait_until_import_is_done():
    for _ in range(60):
        if ImportBatch.objects.last().completed:
            break
        else:
            sleep(1)


def wait_until_true(model_instance: models.Model, attribute_name: str, seconds: int):
    """Checks an attribute of a model until it is 'truthy.' Raises an exception after a given number of seconds of
    trying."""
    for _ in range(seconds):
        model_instance.refresh_from_db()
        if getattr(model_instance, attribute_name) is not None:
            return
        else:
            sleep(1)
    raise Exception(f"'{model_instance}'.'{attribute_name}' never became true after {seconds} seconds.")


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
            for i in range(3):
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
                3,
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

    def test_accept_csv_with_bom(self):
        """Test that Microsoft Excel flavoured CSV files (with byte order mark) work correctly..."""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:

            # Given there's a CSV file that starts with a Byte Order Mark (BOM)
            # https://en.wikipedia.org/wiki/Byte_order_mark#UTF-8
            #
            #
            csv_fd.write(b'\xef\xbb\xbf'.decode('utf-8'))  # <-- THIS

            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(5):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            # When I validate the batch
            #
            #
            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + reverse('importer_narwhal:new-batch'))
            wait(self.browser.find_element_by_css_selector, 'input#id_import_sheet') \
                .send_keys(csv_fd.name)
            Select(self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name')) \
                .select_by_visible_text('Person')
            self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name').submit()
            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Validate Batch"]') \
                .click()
            wait_until_dry_run_is_done()
            self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')

            # Then I should NOT see an error that says "ERROR ...not a valid column name..."
            #
            #
            self.assertNotIn(
                "ERROR",
                self.el('main.container').text
            )

            # When I import the batch
            #
            #
            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Import 5 rows"]') \
                .click()

            wait_until_import_is_done()
            # ... Jump back to the detail page now that the import has completed in the background -- side stepping the
            # ... mid-import page for this test.
            self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')

            # Then I should NOT see an error that says "ERROR ...not a valid column name..."
            #
            #
            self.assertNotIn(
                "ERROR",
                self.el('main.container').text
            )
            # and I should see that the import completed successfully
            self.assertIn(
                "Import completed successfully",
                self.el('main.container').text
            )
            for record in imported_records:
                self.assertIn(
                    record['name'],
                    self.el('main.container').text
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

    @override_settings(DEBUG=True, COMPRESS_ENABLED=True)
    def test_validate_post_validate_errors(self):
        """Test that the Info Card, Status Guide, General Errors Readout, Error Rows, and Error Rows ~Paginator~
        elements are displayed on the batch detail page when in the post-validate-errors state"""

        # Given I've set up a batch from the Import batch setup page containing an erroneous column
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement', 'not_a_legit_column_name'])
            csv_writer.writeheader()
            for i in range(5):
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

        wait_until_dry_run_is_done()
        self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')
        # Confirm we're on the right page now
        wait(self.browser.find_element, By.CSS_SELECTOR, 'div.importer-post-validate-errors')

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
            # Then I should see the Status Guide with a "Start Over" button
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
            # and it should contain 5 row level errors (limited by pagination)
            self.assertEqual(
                5,
                errors_section.text.count("Enter a valid boolean value")
            )
            # # and the row level errors paginator
            # self.browser.find_element(By.CSS_SELECTOR, 'nav[aria-label="Pagination"]')

        # And I should not see the imported rows section
        with self.subTest(msg="No imported rows section"):
            with self.assertRaises(NoSuchElementException):
                self.browser.find_element(By.CSS_SELECTOR, 'div.importer-imported-rows')

    @override_settings(DEBUG=True, COMPRESS_ENABLED=True)
    def test_validate_post_validate_ready(self):
        """Test that the Info Card and Status Guide are displayed and no other elements on the batch detail page
        when in the post-validate-ready state"""

        # Given I've set up a batch from the Import batch setup page that has no erroneous rows or invalid cells
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(3):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'True'
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

        sleep(1)  # Match sleep of redirect javascript
        # Confirm we're on the right page now
        wait(self.browser.find_element, By.CSS_SELECTOR, 'div.importer-post-validate-ready')

        with self.subTest(msg="Status Guide"):
            # Then I should see the Status Guide with an Import X rows button
            status_guide_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-status-guide')
            self.assertIn(
                'No errors were encountered during validation. Ready to import.',
                status_guide_element.text
            )
            status_guide_element.find_element(By.CSS_SELECTOR, 'input[value="Import 3 rows"]')

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

        # And I should not see the errors section
        with self.subTest(msg="No errors section"):
            with self.assertRaises(NoSuchElementException):
                self.browser.find_element(By.CSS_SELECTOR, 'div.importer-errors')

        # And I should not see the imported rows section
        with self.subTest(msg="No imported rows section"):
            with self.assertRaises(NoSuchElementException):
                self.browser.find_element(By.CSS_SELECTOR, 'div.importer-imported-rows')

    @override_settings(DEBUG=True, COMPRESS_ENABLED=True)
    def test_mid_import(self):
        """Test that the Info Card and Status Guide are displayed with a note about import being in progress when in
        the mid-import state"""

        # Given I've set up a batch and validated it successfully
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(3):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'True'
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

            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Validate Batch"]') \
                .click()


            # When I click the "Import X rows button"
            wait_until_dry_run_is_done()
            self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')
            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Import 3 rows"]') \
                .click()

        # ... artificially force batch back into 'mid-import' state
        wait_until_import_is_done()
        batch = ImportBatch.objects.last()
        batch.completed = None
        batch.save()
        # ... and go back to the detail page
        self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')

        with self.subTest(msg="Status Guide"):
            # Then I should see the Status Guide with a message that says "Import in progress"
            status_guide_element = wait(self.browser.find_element, By.CSS_SELECTOR, 'div.importer-status-guide')
            self.assertIn(
                'Import in progress',
                status_guide_element.text
            )

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

    @override_settings(DEBUG=True, COMPRESS_ENABLED=True)
    def test_post_import_failed(self):
        """Test that Info Card, Status Guide, Row Errors, and ~Paginator~ are present but not All Rows when in the
        post-import-failed state"""

        # Given I've set up a batch from the Import batch setup page containing foreign key errors
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['subject_person', 'type', 'object_person'])
            csv_writer.writeheader()
            for i in range(5):
                row = {}
                row['subject_person'] = 1  # <- Doesn't exist
                row['type'] = 'Test Type'
                row['object_person'] = 2  # <- Doesn't exist
                csv_writer.writerow(row)
                imported_records.append(row)
            csv_fd.flush()  # Make sure it's actually written to the filesystem!

            self.log_in(is_administrator=True)
            self.browser.get(self.live_server_url + reverse('importer_narwhal:new-batch'))
            wait(self.browser.find_element_by_css_selector, 'input#id_import_sheet') \
                .send_keys(csv_fd.name)
            Select(self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name')) \
                .select_by_visible_text('PersonRelationship')
            self.browser.find_element(By.CSS_SELECTOR, 'select#id_target_model_name').submit()

            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Validate Batch"]') \
                .click()

            wait_until_dry_run_is_done()
            self.browser.refresh()
            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Import 5 rows"]') \
                .click()

        # Jump back to the detail page now that the import has completed in the background -- side stepping the
        # mid-import page for this test.
        wait_until_import_is_done()
        self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')
        # Confirm we're on the right page now
        wait(self.browser.find_element, By.CSS_SELECTOR, 'div.importer-post-import-failed')

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
                'PersonRelationship',
                info_card_element.text
            )

        with self.subTest(msg="Status Guide"):
            # Then I should see the Status Guide with a "Start Over" button
            status_guide_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-status-guide')
            self.assertIn(
                'Import failed. No records were imported.',
                status_guide_element.text
            )
            status_guide_element.find_element(By.LINK_TEXT, 'Start Over')

        # Then I should see an errors section
        errors_section = wait(self.browser.find_element_by_css_selector, 'div.importer-errors')
        with self.subTest(msg="Error Rows"):
            # and it should contain 5 row level errors
            self.assertEqual(
                5,
                errors_section.text.count("Person matching query does not exist")
            )
            # # and the row level errors paginator
            # self.browser.find_element(By.CSS_SELECTOR, 'nav[aria-label="Pagination"]')

        # And I should not see the imported rows section
        with self.subTest(msg="No imported rows section"):
            with self.assertRaises(NoSuchElementException):
                self.browser.find_element(By.CSS_SELECTOR, 'div.importer-imported-rows')

    @override_settings(DEBUG=True, COMPRESS_ENABLED=True)
    def test_complete(self):
        """Test that Info Card, All Rows, and Status Guide, but not Row Errors are present when in the complete
        state"""

        # Given I've set up a batch from the Import batch setup page containing NO errors
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as csv_fd:
            imported_records = []
            csv_writer = csv.DictWriter(csv_fd, ['name', 'is_law_enforcement'])
            csv_writer.writeheader()
            for i in range(5):
                row = {}
                row['name'] = f'Test Person {uuid4()}'
                row['is_law_enforcement'] = 'checked'
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

            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Validate Batch"]') \
                .click()

            wait_until_dry_run_is_done()
            self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')
            wait(self.browser.find_element, By.CSS_SELECTOR, 'input[value="Import 5 rows"]') \
                .click()

        wait_until_import_is_done()
        # Jump back to the detail page now that the import has completed in the background -- side stepping the
        # mid-import page for this test.
        self.browser.get(self.live_server_url + f'/changing/importer/batch/{ImportBatch.objects.last().pk}')
        # Confirm we're on the right page now
        wait(self.browser.find_element, By.CSS_SELECTOR, 'div.importer-complete')

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
            # Then I should see the Status Guide with a message saying the import completed successfully
            status_guide_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-status-guide')
            self.assertIn(
                'Import completed successfully',
                status_guide_element.text
            )

        with self.subTest(msg='Imported rows section'):
            imported_rows_element = self.browser.find_element(By.CSS_SELECTOR, 'div.importer-imported-rows')
            self.assertIn(
                imported_records[1]['name'],
                imported_rows_element.text
            )


class TestExporterUI(SeleniumFunctionalTestCase):
    @tag('wip')
    def test_export_page_success_scenario(self):
        # GIVEN there's data in the system
        for i in range(10):
            Person.objects.create(name=f"Test Person {i}")

        # When I go to the exporter landing page
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + f'/changing/importer/exports/')

        # It being our first time, there should be a message that says "No exports batches yet"
        self.assertIn(
            "No export batches yet",
            self.el('main.container').text
        )

        # And I click the "Start Export" link
        self.browser.find_element(By.XPATH, '//a[contains(text(), "Start Export")]').click()

        # Then I select Person in the models multiselect
        self.select2_select_by_visible_text('id_models_to_export', 'Person')

        # And I click "Export" -- and take note of the time it started
        self.submit_button_el('Export') \
            .click()
        start_time = datetime.now()

        # Then I should see a page confirming that the export is complete and communicating the status of the export
        # to me
        wait_until_true(ExportBatch.objects.last(), 'completed', 6)
        self.assertIn(
            "Completed",
            self.el('h2').text
        )

        # And I should see info like start time
        self.assertAlmostEqual(
            start_time,
            dateparser.parse(self.el('.datum-started span.value').text),
            delta=timedelta(10)
        )

        # And I take note of the batch number for later reference...
        my_first_batch_number = self.el('.datum-batch-number span.value').text

        # And when I go back to the exporter landing page
        # Then I should see a listing of past and present exports
        # Showing the status of each
        # And when they happened
        self.browser.get(self.live_server_url + f'/changing/importer/exports/')
        self.assertIn(
            'Person',
            self.el('.exports-listing .row-1 .cell-models-to-export').text
        )
        self.assertAlmostEqual(
            start_time,
            dateparser.parse(self.el('.exports-listing .row-1 .cell-started').text),
            delta=timedelta(10)
        )

        # And after doing dozens of batches
        # When I go to the exports landing page
        # I should see a paginator
        for _ in range(36):
            # For expedience make a bunch of phony export batch records
            ExportBatch.objects.create(
                models_to_export=['Grouping', ],  # Not "Person" to distinguish from first batch
                started=timezone.now(),
                completed=timezone.now(),
                export_file=ExportBatch.objects.last().export_file  # Reuse the file from the first import
            )

        self.browser.get(self.live_server_url + f'/changing/importer/exports/')
        self.assertIn(
            "Next",
            self.el('main.container ul.pagination').text
        )

        # And if I go to the last page I see my first export batch
        last_link = self.el('main.container ul.pagination') \
            .find_element(By.XPATH, '//a[contains(text(), "Last")]')
        wait(last_link.click)

        self.assertIn(
            my_first_batch_number,
            self.el('.exports-listing tr:last-child .cell-batch-number').text
        )

    @tag('wip')
    def test_detail_page_export_in_progress(self):
        # GIVEN there's data in the system
        for i in range(10):
            Person.objects.create(name=f"Test Person {i}")

        # When I go to the exporter start page
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + f'/changing/importer/exports/new')

        # Then I select Person in the models multiselect
        self.select2_select_by_visible_text('id_models_to_export', 'Person')

        # And I click "Export" -- and take note of the time it started
        self.submit_button_el('Export') \
            .click()
        import_start_time = datetime.now()

        # Then GIVEN the batch is not complete yet...
        wait_until_true(ExportBatch.objects.last(), 'completed', 16)
        batch = ExportBatch.objects.last()
        batch.completed = None
        batch.save()

        # And I go to the detail page
        self.browser.get(self.live_server_url + f'/changing/importer/exports/{batch.pk}')

        # Then I should see a progress spinner and a "check" button so I can check the status after a while
        self.assertIn(
            "Export in progress",
            self.el('h2').text
        )
        self.assertIn(
            "Click the Check button to update status",
            self.el('main.container').text
        )

        # Then GIVEN the batch has completed...
        batch = ExportBatch.objects.last()
        batch.completed = timezone.now()
        batch.save()
        # And I take note of the time that it completed (non-timezone aware)
        end_time = datetime.now()

        # And I click the Check button...
        self.browser.find_element(By.XPATH, '//a[contains(text(), "Check")]').click()

        # Then the page should show that the batch is complete...
        self.assertIn(
            "Completed",
            self.el('h2').text
        )
        self.assertAlmostEqual(
            end_time,
            dateparser.parse(self.el('.datum-completed span.value').text),
            delta=timedelta(10)
        )

    def test_export_page_model_options(self):
        """Test that the list of available models is correct
        """

        # When I go to the export page
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + f'/changing/importer/exports/new')

        # Then I should be able to select all of the exportable models available
        for model_name in MODEL_ALLOW_LIST:
            self.select2_select_by_visible_text('id_models_to_export', model_name)

    @tag('visual')
    def dormant_test_listing_with_lots_of_models_selected(self):
        """DORMANT visual test. Requires manual inspection. To use:
        Remove 'dormant_' from the beginning of the function name.
        Then check the captured screenshot to evaluate.
        """
        # Given I run an import with LOTS of models select...
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + f'/changing/importer/exports/new')
        for model_name in MODEL_ALLOW_LIST:
            self.select2_select_by_visible_text('id_models_to_export', model_name)
        self.submit_button_el('Export') \
            .click()
        wait_until_true(ExportBatch.objects.last(), 'completed', 6)

        # When I go to the listing page
        self.browser.get(self.live_server_url + f'/changing/importer/exports/')

        # Does it screw up the layout of the page?
        self.take_screenshot_and_dump_html()
