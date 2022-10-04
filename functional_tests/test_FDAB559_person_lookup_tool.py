from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from core.models import (
    Grouping,
    Person, PersonTitle, PersonAlias, PersonIdentifier, PersonGrouping
)
from functional_tests.common import (
    SeleniumFunctionalTestCase,
    wait
)
from supporting.models import Title, PersonRelationshipType, PersonIdentifierType, PersonGroupingType
from django.test import tag


class SeleniumTestCase(SeleniumFunctionalTestCase):

    def test_person_lookup_tool_data_points(self):
        # Given there is a person record in the system with identifiers, groups, titles, aliases
        person = Person.objects.create(name="person-ultrafidianism")
        PersonAlias.objects.create(name="alias-Tlakluit", person=person)
        PersonIdentifier.objects.create(
            identifier="identifier-bigeminal",
            person=person,
            person_identifier_type=PersonIdentifierType.objects.create(name="test PersonIdentifier Type"))
        title = Title.objects.create(name="title-wryly")
        PersonTitle.objects.create(person=person, title=title)
        grouping_1 = Grouping.objects.create(name="grouping-septuplication", is_law_enforcement=True)
        grouping_2 = Grouping.objects.create(name="grouping-condescendingness", is_law_enforcement=True)
        PersonGrouping.objects.create(person=person, grouping=grouping_1)
        PersonGrouping.objects.create(person=person, grouping=grouping_2)

        # Given I'm on the person edit page and I'm interacting with the person relationships subject lookup tool
        self.log_in(is_administrator=True)
        # Given I'm on one of the various instances of the person lookup tool
        given_im_on = [
            {
                'scenario_name': 'Person edit page person relationship object',
                'path': '/changing/persons/add/person/',
                'add_another_xpath': "//*[text()=' Add another relationship']",
                'input_selector': '.personrelationshipform input#id_relationships-0-person_relationship_4',
            },
            {
                'scenario_name': 'Person edit page person relationship subject',
                'path': '/changing/persons/add/person/',
                'add_another_xpath': "//*[text()=' Add another relationship']",
                'input_selector': '.personrelationshipform input#id_relationships-0-person_relationship_1',
            },
            {
                'scenario_name': 'Content page person content',
                'path': '/changing/content/add/content/',
                'add_another_xpath': "//*[text()=' Add another person']",
                'input_selector': '.personform input#id_persons-0-person_name',
            },
            {
                'scenario_name': 'Incident page person incident',
                'path': '/changing/incidents/add/incident/',
                'add_another_xpath': "//*[text()=' Add another person']",
                'input_selector': '.personincidentform input#id_personincidents-0-person_name',
            },
            {
                'scenario_name': 'Incident popup page person incident',
                'path': '/changing/incidents/add/incident/',
                'add_another_xpath': "//*[text()=' Add another person']",
                'input_selector': '.personincidentform input#id_personincidents-0-person_name',
            }
        ]
        for scenario in given_im_on:
            with self.subTest(msg=scenario['scenario_name']):
                self.browser.get(self.live_server_url + scenario['path'])
                self.browser.find_element(By.XPATH, scenario['add_another_xpath']) \
                    .click()
                autocomplete_input = self.el(scenario['input_selector'])

                # When I enter the name of the person
                autocomplete_input.send_keys("person-ultrafidianism")

                # Then I should see the following data points included in the results
                results_list = self.el('ul.ui-autocomplete.personac li.ui-menu-item')
                # Name
                self.assertIn(
                    "person-ultrafidianism",
                    results_list.text
                )
                # Alias
                self.assertIn(
                    "alias-Tlakluit",
                    results_list.text
                )
                # Identifiers
                self.assertIn(
                    "identifier-bigeminal",
                    results_list.text
                )
                # Titles
                self.assertIn(
                    "title-wryly",
                    results_list.text
                )
                # Groups
                self.assertIn(
                    "grouping-septuplication",
                    results_list.text
                )
                self.assertIn(
                    "grouping-condescendingness",
                    results_list.text
                )

    def test_person_lookup_tool_relationships_no_results(self):
        # Given there are no person records in the system
        # Given I'm on the person edit page and I'm interacting with the person relationships subject lookup tool
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')
        self.browser.find_element(By.XPATH, "//*[text()=' Add another relationship']") \
            .click()
        autocomplete_input = self.el('.personrelationshipform input#id_relationships-0-person_relationship_4')
        # When I enter a random term into the search
        autocomplete_input.send_keys("Something completely random that shouldn't match on anything 1664484923")
        # Then I should see a "No matches found" message
        results_list = self.el('ul.ui-autocomplete.personac li.ui-menu-item')
        self.assertIn(
            "No matches found",
            results_list.text
        )

    @tag('wip')
    def test_person_lookup_tool_relationships_max_results(self):
        for i in range(100):
            Person.objects.create(name="acetabuliform")
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')

        self.browser.find_element(By.XPATH, "//*[text()=' Add another relationship']") \
            .click()
        autocomplete_input = self.el('.personrelationshipform input#id_relationships-0-person_relationship_4')
        autocomplete_input.send_keys("acetabuliform")

        self.wait_for('ul.ui-autocomplete.personac li.ui-menu-item')
        results_elements = self.browser.find_elements(By.CSS_SELECTOR, 'ul.ui-autocomplete.personac li.ui-menu-item')
        self.assertEqual(
            35,
            len(results_elements)
        )
