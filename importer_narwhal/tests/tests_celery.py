from django.test import TestCase, SimpleTestCase, tag, RequestFactory, override_settings
from selenium.webdriver.common.by import By
from functional_tests.common import SeleniumFunctionalTestCase
from importer_narwhal.models import ImportBatch
from importer_narwhal.narwhal import do_export, run_export_batch
from importer_narwhal.views import try_celery_task_or_fallback_to_synchronous_call
import io
from unittest.mock import patch, MagicMock
import kombu
from django.contrib import messages as django_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files import File
from importer_narwhal.celerytasks import celery_app
import time
from time import sleep

# If test is being flaky try increasing this number to widen the windows
BATCH_RUN_TIME = 9


class TryCeleryTaskOrFallbackToSynchronousCallTestCase(TestCase):

    # Given that the message broker is down (i.e. Redis is offline)
    # When Redis is down ping() raises an OperationalError exception
    @patch('importer_narwhal.celerytasks.celery_app.control.ping', side_effect=kombu.exceptions.OperationalError)
    def test_message_broker_down(self, mock_ping):
        # and there's a celery task
        @celery_app.task
        def test_celery_task(pk):
            pass
        # and there's a fallback function
        fallback_function = MagicMock()
        # And there's an import batch record
        batch = ImportBatch.objects.create(
            import_sheet=File(io.BytesIO(b"This file left intentionally blank"), name="test_import_sheet.csv")
        )

        # When I call try_celery_task_or_fallback_to_synchronous_call()
        request = RequestFactory().get('/')
        # https://stackoverflow.com/a/71066280/1585572
        SessionMiddleware().process_request(request)
        MessageMiddleware().process_request(request)
        try_celery_task_or_fallback_to_synchronous_call(
            test_celery_task,
            fallback_function,
            batch,
            request
        )

        # Then I should see a warning message saying...
        messages = list(django_messages.get_messages(request))
        self.assertIn(
            "Message broker unavailable",
            messages[0].message
        )
        # And "Falling back to synchronous mode"
        self.assertIn(
            "Falling back to synchronous mode",
            messages[0].message
        )
        # And the fallback function should have been called
        fallback_function.assert_called()

    # Given that celery is down but the message broker is not (i.e. Redis is online, but the celery service isn't
    # running). When Celery is down, ping() returns an empty list.
    @patch('importer_narwhal.celerytasks.celery_app.control.ping', return_value=[])
    def test_celery_down(self, mock_ping):
        # and there's a celery task
        @celery_app.task
        def test_celery_task(pk):
            pass
        # and there's a fallback function
        fallback_function = MagicMock()
        # And there's an import batch record
        batch = ImportBatch.objects.create(
            import_sheet=File(io.BytesIO(b"This file left intentionally blank"), name="test_import_sheet.csv")
        )

        # When I call try_celery_task_or_fallback_to_synchronous_call()
        request = RequestFactory().get('/')
        # https://stackoverflow.com/a/71066280/1585572
        SessionMiddleware().process_request(request)
        MessageMiddleware().process_request(request)
        try_celery_task_or_fallback_to_synchronous_call(
            test_celery_task,
            fallback_function,
            batch,
            request
        )

        # Then I should see a warning message saying...
        messages = list(django_messages.get_messages(request))
        self.assertIn(
            "No Celery workers found. Is the Celery daemon running?",
            messages[0].message
        )
        # And "Falling back to synchronous mode"
        self.assertIn(
            "Falling back to synchronous mode",
            messages[0].message
        )
        # And the fallback function should have been called
        fallback_function.assert_called()


# Keep track of unmocked version of run_export_batch before patching it, so we can call it within the wrapper
# mock_expensive_run_export_batch
unmocked_run_export_batch = run_export_batch


def mock_expensive_run_export_batch(export_batch):
    """Add an extra delay before calling run_export_batch()
    """
    sleep(BATCH_RUN_TIME)
    unmocked_run_export_batch(export_batch)


class TestBackgroundTasks(SeleniumFunctionalTestCase):

    def _wait_for(self, element_selector, contains, max_seconds):
        """Call a given function repeatedly until it doesn't raise AssertionError or WebDriverException.
        Gives up after a few tries.
        """
        start_time = time.time()
        while True:
            try:
                if contains not in self.browser.find_element(By.CSS_SELECTOR, element_selector).text:
                    raise Exception
                return time.time() - start_time
            except Exception as e:
                if time.time() - start_time > max_seconds:
                    raise Exception(
                        f"Waited {max_seconds} seconds but didn't see an "
                        f"element '{element_selector}' containing '{contains}'"
                    )
                time.sleep(1)

    @patch('importer_narwhal.views.run_export_batch', mock_expensive_run_export_batch)
    @patch('importer_narwhal.celerytasks.run_export_batch', mock_expensive_run_export_batch)
    @patch('importer_narwhal.views.celery_app.control.ping', return_value=[])  # <- no Celery workers
    @patch('importer_narwhal.views.background_run_export_batch.delay')
    def test_export_post_hangs_until_complete_when_celery_unavailable(
            self,
            mock_views_background_run_export_batch_delay,
            mock_run_export_batch_celery_app_control_ping):
        """Test that when Celery is unavailable the exporter hangs until the batch is complete
        """
        # When I go to the exporter start page
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + f'/changing/importer/exports/new')

        # Then I select Person in the models multiselect
        self.select2_select_by_visible_text('id_models_to_export', 'Person')

        # And I click "Export" -- and take note of the time it started
        self.submit_button_el('Export') \
            .click()

        mock_run_export_batch_celery_app_control_ping.assert_called()
        mock_views_background_run_export_batch_delay.assert_not_called()

        sleep(BATCH_RUN_TIME/3)
        # Still on batch setup page after clicking the "Export" button...
        self.assertIn(
            'Export batch setup',
            self.el('h1').text
        )

        sleep(BATCH_RUN_TIME)
        # It's finally done now
        self._wait_for('h2', 'Complete', BATCH_RUN_TIME/3)

        self.assertIn(
            "Falling back to synchronous mode",
            self.browser.page_source
        )

    @patch('importer_narwhal.views.run_export_batch', mock_expensive_run_export_batch)
    @patch('importer_narwhal.celerytasks.run_export_batch', mock_expensive_run_export_batch)
    @patch('importer_narwhal.views.celery_app.control.ping', return_value=['phony_worker1'])
    @patch('importer_narwhal.views.background_run_export_batch.delay')
    def test_export_post_returns_immediately_when_celery_available(
            self,
            mock_views_background_run_export_batch_delay,
            mock_run_export_batch_celery_app_control_ping):
        """Test that when Celery is available and I submit an export the system doesn't hang for the duration of the
        batch, but instead returns immediately with a status page.
        """
        # When I go to the exporter start page
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + f'/changing/importer/exports/new')

        # Then I select Person in the models multiselect
        self.select2_select_by_visible_text('id_models_to_export', 'Person')

        # And I click "Export" -- and take note of the time it started
        self.submit_button_el('Export') \
            .click()

        mock_run_export_batch_celery_app_control_ping.assert_called()
        mock_views_background_run_export_batch_delay.assert_called()

        self._wait_for('h2', 'Export in progress', BATCH_RUN_TIME/3)
