from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from core.models import (
    Person, PersonTitle, PersonIdentifier, Grouping,
)
from functional_tests.common import (
    SeleniumFunctionalTestCase,
    wait,
)
from sourcing.models import Content
from supporting.models import Title, PersonIdentifierType, PersonRelationshipType, GroupingRelationshipType
from django.test import TestCase, tag
from unittest import skip


class SeleniumTestCase(SeleniumFunctionalTestCase):
    def test_contentcase(self):
        """ContentCase dates not showing on officer profile page right now. For now check create and update pages."""

        # Given there is an existing officer record
        officer = Person.objects.create(name="Test Officer", is_law_enforcement=True)
        # And I go to the create new content page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/content/add/content/')

        # And I set the ended_unknown_date box to checked
        self.input('cases-0-ended_unknown_date').click()  # <-- THIS

        # And I set a start date
        start_date_section = self.el('div#f_id_cases-0-case_opened_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # And I link the officer to the incident
        self.browser.find_element(By.XPATH, "//*[text()=' Add another person']") \
            .click()
        self.enter_autocomplete_data(
            '.personform input#id_persons-0-person_name',
            'ul.ui-autocomplete.personac li.ui-menu-item',
            'Test Officer'
        )

        # And I save the new record
        self.submit_button('Save').click()

        # THEN there should be no validation errors
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        # When I go to the update page (rather than the profile page)
        # Because the profile page doesn't display dates atm
        self.browser.get(self.live_server_url + f'/changing/content/update/content/{Content.objects.last().pk}/')
        # Then the ended unknown date check-box should be checked
        self.assertTrue(
            self.input('cases-0-ended_unknown_date').is_selected()
        )

    def test_incident(self):
        # Given there is an existing officer record & and group record
        officer = Person.objects.create(name="Test Officer", is_law_enforcement=True)
        group = Grouping.objects.create(name="Test Group", is_law_enforcement=True)
        # And I go to the create new incident page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/incidents/add/incident/')
        # And I set the ended_unknown_date box to checked
        self.input('ended_unknown_date').click()  # <-- THIS

        # And I set a start date
        start_date_section = self.el('div#f_id_incident_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # And I link the officer to the incident
        self.browser.find_element(By.XPATH, "//*[text()=' Add another person']") \
            .click()
        self.enter_autocomplete_data(
            '.personincidentform input#id_personincidents-0-person_name',
            'ul.ui-autocomplete.personac li.ui-menu-item',
            'Test Officer'
        )
        # And I link the group to the incident
        self.browser.find_element(By.XPATH, "//*[text()=' Add another grouping']") \
            .click()
        self.enter_autocomplete_data(
            '.groupingincidentform input#id_groupingincidents-0-grouping_name',
            'ul.ui-autocomplete.groupingac li.ui-menu-item',
            'Test Group'
        )
        # And I save the new record
        self.submit_button('Save').click()
        # THEN there should be no validation errors
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        with self.subTest(msg="Officer profile page"):
            # When I go to the officer's profile page
            #
            self.browser.get(self.live_server_url + f'/officer/{officer.pk}')
            # Then I should see the incident named by a date span including "until unknown-end-date"
            self.assertIn(
                'until unknown-end-date',
                self.el('div.incident h3').text
            )

        with self.subTest(msg="Command profile page"):
            # When I go to the group's profile page
            #
            self.browser.get(self.live_server_url + f'/command/{group.pk}')
            # Then I should see the incident named by a date span including "until unknown-end-date"
            self.assertIn(
                'until unknown-end-date',
                self.el('div.command-misconduct button.heading').text
            )

        with self.subTest(msg="Django admin Incident listing page"):
            # When I go to the django admin listing page
            #
            self.browser.get(self.live_server_url + f'/admin/core/incident/')
            # Then I should see the incident named by a date span including "until unknown-end-date"
            self.assertIn(
                'until unknown-end-date',
                self.el('table#result_list tbody tr th').text
            )

    def test_incident_at_least_since(self):
        # Migrating Incident model to use AbstractFuzzyDateSpan. Test that it adds "at least since" to the model too.
        # Given there is an existing officer record & and group record
        officer = Person.objects.create(name="Test Officer", is_law_enforcement=True)
        group = Grouping.objects.create(name="Test Group", is_law_enforcement=True)
        # And I go to the create new incident page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/incidents/add/incident/')
        # And I set the ended_unknown_date box to checked
        self.input('at_least_since').click()  # <-- THIS

        # And I set a start date
        start_date_section = self.el('div#f_id_incident_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # And I link the officer to the incident
        self.browser.find_element(By.XPATH, "//*[text()=' Add another person']") \
            .click()
        self.enter_autocomplete_data(
            '.personincidentform input#id_personincidents-0-person_name',
            'ul.ui-autocomplete.personac li.ui-menu-item',
            'Test Officer'
        )

        # And I link the group to the incident
        self.browser.find_element(By.XPATH, "//*[text()=' Add another grouping']") \
            .click()
        self.enter_autocomplete_data(
            '.groupingincidentform input#id_groupingincidents-0-grouping_name',
            'ul.ui-autocomplete.groupingac li.ui-menu-item',
            'Test Group'
        )

        # And I save the new record
        self.submit_button('Save').click()

        # THEN there should be no validation errors
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        with self.subTest(msg="Officer profile page"):
            # When I go to the officer's profile page
            #
            self.browser.get(self.live_server_url + f'/officer/{officer.pk}')
            # Then I should see the incident named by a date span including "at least since"
            self.assertIn(
                'At least since',
                self.el('div.incident h3').text
            )

        with self.subTest(msg="Command profile page"):
            # When I go to the group's profile page
            #
            self.browser.get(self.live_server_url + f'/command/{group.pk}')
            # Then I should see the incident named by a date span including "until unknown-end-date"
            self.assertIn(
                'At least since',
                self.el('div.command-misconduct button.heading').text
            )

        with self.subTest(msg="Django admin Incident listing page"):
            # When I go to the django admin listing page
            #
            self.browser.get(self.live_server_url + f'/admin/core/incident/')
            # Then I should see the incident named by a date span including "until unknown-end-date"
            self.assertIn(
                'at least since',
                self.el('table#result_list tbody tr th').text
            )

    def test_grouping_relationship(self):
        """Relationship dates not showing on group profile page right now. For now check update changing pages."""
        # Given there's an existing grouping
        Grouping.objects.create(name="Existing Grouping", is_law_enforcement=True)
        # Given there's an existing grouping relationship type
        GroupingRelationshipType.objects.create(name="Group Relationship Type")

        # Given I go to the create new grouping page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/groupings/add/grouping/')

        # And I add a new relationship
        self.browser.find_element(By.XPATH, "//*[text()=' Add another relationship']") \
            .click()
        # And I set the relationship type
        self.select_list('relationships-0-grouping_relationship_2') \
            .select_by_visible_text('Group Relationship Type')

        # ... other grouping
        self.enter_autocomplete_data(
            '.groupingrelationshipform input#id_relationships-0-grouping_relationship_4',
            'ul.ui-autocomplete.groupingac li.ui-menu-item',
            'Existing Grouping'
        )

        # And I set the ended_unknown_date box to checked
        self.input('relationships-0-ended_unknown_date').click()  # <-- THIS

        # And I set a start date
        start_date_section = self.el('div#f_id_relationships-0-grouping_relationship_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # ... is law enforcement
        self.select_list('law_enforcement') \
            .select_by_visible_text('Yes')

        # ... group name
        self.input('name').send_keys('New Group dolesomeness')

        # And I save the new record
        self.submit_button('Save').click()

        # THEN there should be no validation errors
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        # When I go to the update page (rather than the profile page)
        # Because the profile page doesn't display dates atm
        self.browser.get(self.live_server_url + f'/changing/groupings/update/grouping/{Grouping.objects.last().pk}/')
        # Then the ended unknown date check-box should be checked
        self.assertTrue(
            self.input('relationships-0-ended_unknown_date').is_selected()
        )

    def test_person_grouping(self):
        # Given there's an existing grouping
        Grouping.objects.create(name="Test Grouping", is_law_enforcement=True)

        # Given I go to the create new officer page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')

        # And I add a new group
        self.browser.find_element(By.XPATH, "//*[text()=' Add another grouping']") \
            .click()

        # And I set the ended_unknown_date box to checked
        self.input('persongroupings-0-ended_unknown_date').click()  # <-- THIS

        # And I set a start date
        start_date_section = self.el('div#f_id_persongroupings-0-person_grouping_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # ... grouping
        self.enter_autocomplete_data(
            '.persongroupingform input#id_persongroupings-0-grouping_name',
            'ul.ui-autocomplete.groupingac li.ui-menu-item',
            'Test Grouping'
        )

        # ... is law enforcement
        self.select_list('law_enforcement') \
            .select_by_visible_text('Yes')

        # And I save the new record
        self.submit_button('Save').click()

        # THEN there should be no validation errors
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        # When I go to the profile page
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')

        # Then I should see a new person relationship with date span from ... "until unknown-end-date"
        self.assertIn(
            'until unknown-end-date',
            self.browser.find_element(By.CSS_SELECTOR, 'section.identification ul#commands').text
        )

    # Having trouble getting the ended unknown date checkbox field to show in the edit interface
    # Skipping for now because this is a low priority
    def test_person_payment(self):
        # Given I go to the create new officer page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')

        # And I add a new payroll
        self.browser.find_element(By.XPATH, "//*[text()=' Add another payroll']") \
            .click()

        # And I set the ended_unknown_date box to checked
        self.input('payments-0-ended_unknown_date').click()  # <-- THIS

        # And I set a start date
        start_date_section = self.el('td#f_id_payments-0-person_payment_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # ... is law enforcement
        self.select_list('law_enforcement') \
            .select_by_visible_text('Yes')

        # And I save the new record
        self.submit_button('Save').click()

        # THEN there should be no validation errors
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        # When I go to the profile page
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')

        # And open the payroll accordion
        self.el('section.payroll div#accordion').click()

        # Then I should see a new person relationship with date span from ... "until unknown-end-date"
        self.assertIn(
            'until unknown-end-date',
            self.el('div.payrollcontainer td.field-date_span_str').text
        )

    def test_person_relationship(self):
        # Given there's an existing person
        other_person = Person.objects.create(name="Other Person", is_law_enforcement=True)

        # Given there's an existing person relationship type
        PersonRelationshipType.objects.create(name='test relationship type')

        # Given I go to the create new officer page
        b = self.browser
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')

        # And I add a new PersonRelatiponship
        self.browser.find_element(By.XPATH, "//*[text()=' Add another relationship']") \
            .click()

        # And I set the ended_unknown_date box to checked
        self.input('relationships-0-ended_unknown_date').click()  # <-- THIS

        # And I set a start date
        start_date_section = self.el('div#f_id_relationships-0-person_relationship_started_0')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
            .send_keys('1')
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
        start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
            .send_keys('2000')

        # and I fill any other necessary fields ...
        # ... relationship type
        self.select_list('relationships-0-person_relationship_2') \
            .select_by_visible_text('test relationship type')

        # ... other officer
        self.enter_autocomplete_data(
            '.personrelationshipform input#id_relationships-0-person_relationship_4',
            'ul.ui-autocomplete.personac li.ui-menu-item',
            "Other Person"
        )

        # ... is law enforcement
        self.select_list('law_enforcement') \
            .select_by_visible_text('Yes')

        # And I save the new record
        self.submit_button('Save').click()

        # THEN there should be no validation errors
        with self.assertRaises(NoSuchElementException):
            error = self.browser.find_element(By.CSS_SELECTOR, 'ul.errorlist').text
            print(f"Validation error found: '{error}'")

        # When I go to the profile page
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')

        # Then I should see a new person relationship with date span from ... "until unknown-end-date"
        self.assertIn(
            'until unknown-end-date',
            self.browser.find_element(By.CSS_SELECTOR, 'section.associates ul#relationships').text
        )

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
        start_date_section = self.el('div#f_id_identifiers-0-identifier_started_0')
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
        self.select_list('identifiers-0-person_identifier_type') \
            .select_by_visible_text('person-identifier-type-ammocoetoid')
        self.input('identifiers-0-identifier').send_keys('TEST IDENTIFIER VALUE')
        self.select_list('law_enforcement') \
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
        self.select_list('titles-0-title') \
            .select_by_visible_text('title-ammocoetoid')
        self.select_list('law_enforcement') \
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


class UnitTests(TestCase):
    def test_models_persontitle(self):
        # Given there's an existing Title type
        title = Title.objects.create(name="title-ammocoetoid")
        # Given there's an existing Person record
        person = Person.objects.create(name="person-mnemotechnist")
        # Given I create a new model instance of a PersonTitle,
        # with the ended_unknown_date set to True
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

    def test_person_identifier(self):
        # Given there's an existing identifier type
        person_identifier_type = PersonIdentifierType.objects.create(name='person-identifier-type-test')
        # Given there's an existing Person record
        person = Person.objects.create(name="person-test")
        # Given I create a new model instance of a PersonIdentifier,
        # with the ended_unknown_date set to True
        PersonIdentifier.objects.create(
            ended_unknown_date=True,
            person=person,
            person_identifier_type=person_identifier_type
        )
        # When I load the new instance
        # Then I should see ended_unknown_date set to True
        self.assertEqual(
            True,
            PersonIdentifier.objects.last().ended_unknown_date
        )
