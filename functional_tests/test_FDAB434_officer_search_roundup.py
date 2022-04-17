from unittest import skip

from selenium.webdriver.common.by import By

from core.models import Person
from functional_tests.common import wait, SeleniumFunctionalTestCase
from faker import Faker
faker = Faker()


class MySeleniumTestCase(SeleniumFunctionalTestCase):
    def test_officer_search_page(self):
        # Given there is an officer record named "Miesha Britton"
        Person.objects.create(name="Miesha Britton", is_law_enforcement=True)
        # and there are a number of other officer records in the system
        for i in range(100):
            Person.objects.create(name=faker.name(), is_law_enforcement=True)

        # When I do a search for "Miesha Britton"
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        self.assertNotIn(
            'Not Found',
            self.browser.page_source
        )
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Miesha Britton")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then the page should return a list of results
        # and the record "Miesha Britton" should be the first in the list
        first_result = self.browser.find_element(By.CSS_SELECTOR, "ul.results li.row-1")
        self.assertIn(
            "Miesha Britton",
            first_result.text
        )

        with self.subTest(msg="Officer links"):
            # When I click the officer link
            first_result.find_element(By.CSS_SELECTOR, 'a.profile-link') \
                .click()
            # Then I should be taken to their officer profile page
            self.assertIn(
                "Miesha Britton",
                wait(self.browser.find_element, By.CSS_SELECTOR, '#content h1').text
            )
