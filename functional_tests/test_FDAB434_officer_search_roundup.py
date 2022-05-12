from unittest import skip

from selenium.webdriver.common.by import By

from core.models import Person, PersonAlias, PersonIdentifier, Grouping, PersonGrouping, PersonTitle
from fdpuser.models import FdpUser
from functional_tests.common import wait, SeleniumFunctionalTestCase
from faker import Faker

from profiles.models import OfficerSearch
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
        first_result = self.browser.find_element(By.CSS_SELECTOR, "div.search-results li.row-1")
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

    def test_search_results_number_of_results(self):
        # Given there are 314 records in the system with the same name
        for _ in range(314):
            Person.objects.create(name='polyonychia', is_law_enforcement=True)

        # When I search for them
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("polyonychia")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then the number of results should say "314"
        self.assertIn(
            '314',
            self.browser.find_element(By.CSS_SELECTOR, "span.number-of-results").text
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
        first_result = self.browser.find_element(By.CSS_SELECTOR, "div.search-results li.row-1")
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
        first_result = self.browser.find_element(By.CSS_SELECTOR, "div.search-results li.row-1")
        self.assertIn(
            "bathmic",
            first_result.text
        )
        self.assertIn(
            "intertarsal",
            first_result.text
        )

    def test_search_results_rows_current_rank(self):
        # Given there is an officer record with ranks, two of which (miasmatical & pompoleon) has
        # all of the end dates set to zeros (day, month, year).
        person_record = Person.objects.create(name="Christopher Mills", is_law_enforcement=True)
        PersonTitle.objects.create(
            title=Title.objects.create(name='ferulic'),
            person=person_record,
            start_day=1,
            start_month=1,
            start_year=2001,

            end_day=2,
            end_month=1,
            end_year=0,

            at_least_since=True
        )
        PersonTitle.objects.create(
            title=Title.objects.create(name='miasmatical'),
            person=person_record,
            start_day=3,
            start_month=1,
            start_year=2001,

            end_day=0,
            end_month=0,
            end_year=0,

            at_least_since=True
        )
        PersonTitle.objects.create(
            title=Title.objects.create(name='pompoleon'),
            person=person_record,
            start_day=3,
            start_month=1,
            start_year=2000,

            end_day=0,
            end_month=0,
            end_year=0,

            at_least_since=True
        )
        PersonTitle.objects.create(
            title=Title.objects.create(name='thyrsoidal'),
            person=person_record,
            start_day=5,
            start_month=1,
            start_year=2001,

            end_day=6,
            end_month=0,
            end_year=2001,

            at_least_since=True
        )
        PersonTitle.objects.create(
            title=Title.objects.create(name='ungodlily'),
            person=person_record,
            start_day=5,
            start_month=1,
            start_year=2001,

            end_day=1,
            end_month=0,
            end_year=0,

            at_least_since=True
        )

        # When I do a search for the officer
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Christopher Mills")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then I should see ONLY the titles with end dates set to all zeros
        first_result = self.browser.find_element(By.CSS_SELECTOR, "div.search-results li.row-1")
        self.assertIn(
            "miasmatical",
            first_result.text
        )
        self.assertIn(
            "pompoleon",
            first_result.text
        )
        self.assertNotIn(
            "thyrsoidal",
            first_result.text
        )
        self.assertNotIn(
            "ferulic",
            first_result.text
        )
        self.assertNotIn(
            "ungodlily",
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
        first_result = self.browser.find_element(By.CSS_SELECTOR, "div.search-results li.row-1")
        self.assertIn(
            "subcommissaryship",
            first_result.text
        )
        self.assertIn(
            "withindoors",
            first_result.text
        )

    def test_blank_search_new_record_listed_first(self):
        # Given there are a number of officers in the system and I add one more
        for i in range(100):
            Person.objects.create(name=faker.name(), is_law_enforcement=True)
        Person.objects.create(name="microcosmography", is_law_enforcement=True)

        # When I go to the search page (without doing a search)
        self.log_in(is_administrator=False)
        self.browser.get(self.live_server_url + '/officer/search-roundup')

        # Then I should see the newly added officer as the first result
        first_result = self.browser.find_element(By.CSS_SELECTOR, "div.search-results li.row-1")
        self.assertIn(
            "microcosmography",
            first_result.text
        )

    def test_query_logging(self):
        """Ensure that logs are recorded of user's searches
        """
        # Given I'm logged in as a user
        self.log_in(is_administrator=False)
        # When I perform a search
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("zephyry")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then I should see a new OfficerSearch record created
        self.assertEqual(
            1,
            OfficerSearch.objects.count()
        )
        # Then it should contain my search query
        self.assertIn(
            'zephyry',
            OfficerSearch.objects.last().parsed_search_criteria
        )
        # Then it should contain my user id
        self.assertEqual(
            FdpUser.objects.last(),
            OfficerSearch.objects.last().fdp_user
        )
