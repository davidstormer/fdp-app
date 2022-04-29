from unittest import skip

from selenium.webdriver.common.by import By

from core.models import Person, PersonAlias, PersonIdentifier, Grouping, PersonGrouping, PersonTitle
from functional_tests.common import wait, SeleniumFunctionalTestCase
from faker import Faker

from supporting.models import PersonIdentifierType, PersonGroupingType, Title

faker = Faker()


class MySeleniumTestCase(SeleniumFunctionalTestCase):
    def test_officer_search_page_success_scenario(self):
        # Given there is an officer record named "Miesha Britton"
        Person.objects.create(name="Miesha Britton", is_law_enforcement=True)
        # and there are a number of other officer records in the system
        for i in range(100):
            Person.objects.create(name=faker.name(), is_law_enforcement=True)

        # When I do a search for "Miesha Britton"
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')
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

    def test_search_results_rows_aliases(self):
        # Given there is an officer record with aliases
        person_record = Person.objects.create(name="Daniel Wilson", is_law_enforcement=True)
        PersonAlias.objects.create(name="contortioned", person=person_record)
        PersonAlias.objects.create(name="pompoleon", person=person_record)

        # When I do a search for the officer
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Daniel Wilson")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then I should see their aliases printed in their search result row
        first_result = self.browser.find_element(By.CSS_SELECTOR, "ul.results li.row-1")
        self.assertIn(
            "contortioned",
            first_result.text
        )
        self.assertIn(
            "pompoleon",
            first_result.text
        )

    def test_search_results_rows_identifiers(self):
        # Given there is an officer record with identifiers
        person_record = Person.objects.create(name="Joel Lindsey", is_law_enforcement=True)
        id_type = PersonIdentifierType.objects.create(name='Test Type')
        PersonIdentifier.objects.create(
            identifier='bathmic', person=person_record,
            person_identifier_type=id_type)
        PersonIdentifier.objects.create(
            identifier='intertarsal', person=person_record,
            person_identifier_type=id_type)

        # When I do a search for the officer
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Joel Lindsey")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then I should see their identifiers printed in their search result row
        first_result = self.browser.find_element(By.CSS_SELECTOR, "ul.results li.row-1")
        self.assertIn(
            "bathmic",
            first_result.text
        )
        self.assertIn(
            "intertarsal",
            first_result.text
        )

    def test_search_results_rows_commands(self):
        # Given there is an officer record with commands
        person_record = Person.objects.create(name="Kayla Ellis", is_law_enforcement=True)
        person_grouping_type = PersonGroupingType.objects.create(name="pgtype")
        PersonGrouping.objects.create(
            type=person_grouping_type,
            person=person_record,
            grouping=Grouping.objects.create(name=f"subcommissaryship"))
        PersonGrouping.objects.create(
            type=person_grouping_type,
            person=person_record,
            grouping=Grouping.objects.create(name=f"withindoors"))

        # When I do a search for the officer
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Kayla Ellis")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then I should see their commands printed in their search result row
        first_result = self.browser.find_element(By.CSS_SELECTOR, "ul.results li.row-1")
        self.assertIn(
            "subcommissaryship",
            first_result.text
        )
        self.assertIn(
            "withindoors",
            first_result.text
        )
