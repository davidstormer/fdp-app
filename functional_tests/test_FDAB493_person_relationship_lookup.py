from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from core.models import (
    Grouping,
    Person
)
from functional_tests.common import (
    SeleniumFunctionalTestCase,
    wait
)
from supporting.models import Title, PersonRelationshipType
from django.test import override_settings


class SeleniumTestCase(SeleniumFunctionalTestCase):
    def test_person_relationship(self):
        # GIVEN
        # Given there's a person relationship type record
        # NOTE: 'Patrol Partner' necessary for test to pass if code in state before fix from FDAB-340
        PersonRelationshipType.objects.create(name='Patrol Partner')
        # Given there's a person record
        Person.objects.create(name="person-naphthalenic", is_law_enforcement=True)
        # Given I'm logged into the system as an Admin
        b = self.browser
        self.log_in(is_administrator=True)
        # Given I'm on the new person edit page
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')

        # WHEN on a new relationship I select a type and the person
        self.browser.find_element(By.XPATH, "//*[text()=' Add another relationship']") \
            .click()
        Select(self.browser.find_element(
            By.CSS_SELECTOR, '.personrelationshipform select#id_relationships-0-person_relationship_2')) \
            .select_by_visible_text('Patrol Partner')

        self.enter_autocomplete_data(
            '.personrelationshipform input#id_relationships-0-person_relationship_4',
            'ul.ui-autocomplete.personac li.ui-menu-item',
            "person-naphthalenic"
        )

        # ... and other necessary fields ...
        Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
            .select_by_visible_text('Yes')
        b.find_element(By.CSS_SELECTOR, 'input[name="name"]')\
            .send_keys('Kidderminster')

        # ...   and save
        b.find_element(By.CSS_SELECTOR, "input[value='Save']").click()

        # THEN there should be no validation errors reported by the system
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        # THEN the officer profile should show the relationship
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')
        self.assertIn(
            'Patrol Partner',
            self.browser.find_element(By.CSS_SELECTOR, 'section.associates').text
        )
