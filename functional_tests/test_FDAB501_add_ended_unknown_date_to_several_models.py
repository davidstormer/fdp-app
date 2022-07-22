from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from core.models import (
    Person, PersonTitle,
)
from functional_tests.common import (
    SeleniumFunctionalTestCase,
    wait,
)
from supporting.models import Title, PersonIdentifierType
from django.test import TestCase


### Title
class SeleniumTestCase(SeleniumFunctionalTestCase):
    def test_person_identifier(self):
        # Given there's an existing Title type
        person_identifier_type = PersonIdentifierType.objects.create(name="person-identifier-type-ammocoetoid")
        # Given I go to the new officer page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')
        # And I add a person identifier
        self.browser.find_element(By.XPATH, "//*[text()=' Add another identifier']") \
            .click()
        # And I set the ended_unknown_date box to checked
        self.input('identifiers-0-ended_unknown_date').click()
        # And I set a start date
        start_date_section = self.el('div#f_id_identifiers-0-person_identifier_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # ... and I fill any other necessary fields ...
        Select(self.el_select('identifiers-0-identifier')) \
            .select_by_visible_text('person-identifier-type-ammocoetoid')
        Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
            .select_by_visible_text('Yes')
        b.find_element(By.CSS_SELECTOR, 'input[name="name"]')\
            .send_keys('person-name-electrocardiographic')
        # And I save the new record
        self.submit_button('Save').click()
        # THEN there should be no validation errors reported by the system
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")
        # When I go to the profile page
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')
        # Then I should see the person title dates span from ... "until unknown-end-date"
        self.assertIn(
            'until unknown-end-date',
            self.browser.find_element(By.CSS_SELECTOR, 'section.identification ul.identifiers').text
        )
        self.take_screenshot_and_dump_html()

    def test_person_title(self):
        # Given there's an existing Title type
        title = Title.objects.create(name="title-ammocoetoid")
        # Given I go to the new officer page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')
        # And I add a person title
        self.browser.find_element(By.XPATH, "//*[text()=' Add another title']") \
            .click()
        # And I set the ended_unknown_date box to checked
        self.input('titles-0-ended_unknown_date').click()
        # And I set a start date
        start_date_section = self.el('div#f_id_titles-0-person_title_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # ... and I fill any other necessary fields ...
        Select(self.el_select('titles-0-title')) \
            .select_by_visible_text('title-ammocoetoid')
        Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
            .select_by_visible_text('Yes')
        b.find_element(By.CSS_SELECTOR, 'input[name="name"]')\
            .send_keys('person-name-psychorhythmia')
        # And I save the new record
        self.submit_button('Save').click()
        # THEN there should be no validation errors reported by the system
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")
        # When I go to the profile page
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')
        # Then I should see the person title dates span from ... "until unknown-end-date"
        self.assertIn(
            'until unknown-end-date',
            self.browser.find_element(By.CSS_SELECTOR, 'section.identification ul.titles').text
        )
        self.take_screenshot_and_dump_html()


class UnitTests(TestCase):
    def test_models_persontitle(self):
        # Given there's an existing Title type
        title = Title.objects.create(name="title-ammocoetoid")
        # Given there's an existing Person record
        person = Person.objects.create(name="person-mnemotechnist")
        # Given I create a new model instance of a PersonTitle, the ended_unknown_date set to True
        PersonTitle.objects.create(
            ended_unknown_date=True,
            person=person,
            title=title
        )
        # When I load the new instance
        # Then I should see ended_unknown_date set to True
        self.assertEqual(
            True,
            PersonTitle.objects.last().ended_unknown_date
        )
