from django.test import tag
from django.urls import reverse
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from core.models import Person, Grouping, Incident
from functional_tests.common import (
    SeleniumFunctionalTestCase
)
from sourcing.models import Content
from functional_tests.factories import factories


class DeleteButtonsSeleniumTestCase(SeleniumFunctionalTestCase):
    def test_success_scenario(self):
        models_to_test = [Person, Content, Grouping, Incident]

        b = self.browser
        self.log_in(is_administrator=True)

        for model in models_to_test:
            with self.subTest(msg=f"{model}"):
                # Given there's an existing content record
                record = factories[model.__name__]()
                # record = model.objects.create(name="Test record to delete")
                record_pk = record.pk
                # And I'm on the content edit page (custom, not django admin)
                if model.__name__ != 'Incident':
                    self.browser.get(
                        self.live_server_url + reverse(f'changing:edit_{model.__name__.lower()}', kwargs={"pk": record_pk})
                     )
                elif model.__name__ == 'Incident':
                    path = reverse(
                        f'changing:edit_{model.__name__.lower()}',
                        kwargs={"pk": record_pk, "content_id": 0}
                    )
                    self.browser.get(
                        self.live_server_url + path
                     )

                # When I click the delete button
                self.el('.submit-row a.deletelink').click()

                # Then I should be taken to the Django admin delete page
                self.assertIn(
                    "Are you sure you want to delete the",
                    self.browser.page_source
                )

                # When I click the "Yes, I'm sure" button
                self.submit_button("Yes, I’m sure").click()

                # Then I should see a confirmation ..."was deleted successfully."
                self.assertIn(
                    "was deleted successfully.",
                    self.browser.page_source
                )
                # Then the content record should not exist in the system
                with self.assertRaises(model.DoesNotExist):
                    model.objects.get(pk=record_pk)

    def test_not_visible_on_create_pages(self):
        """Test that the delete button is not shown on a create page
        """

        models_to_test = [Person, Content, Grouping, Incident]

        b = self.browser
        self.log_in(is_administrator=True)

        for model in models_to_test:
            with self.subTest(msg=f"{model}"):
                self.browser.get(self.live_server_url + reverse(f'changing:add_{model.__name__.lower()}'))
                self.wait_for('div.submit-row')
                with self.assertRaises(NoSuchElementException, msg="Delete button found on create page"):
                    self.browser.find_element(By.CSS_SELECTOR, '.submit-row a.deletelink')
