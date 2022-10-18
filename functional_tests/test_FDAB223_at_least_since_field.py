"""Functional tests to ensure that terminology "as of" is changed to "at least since" on date spans.

TODO:
- test_profile_at_least_since_on_person_relationship is disabled temporarily until FDAB-117 is merged
- No test for "at least since" showing on the group profile page in listing of related groups. This is because dates
are currently not printed at the time of writing (Feb 2 2022).
- test_at_least_since_edit_from_person_edit_page_person_releationship is disabled temporarily until FDAB-340 is
resolved.

-- Tristan Chambers
"""

from unittest import skip
from uuid import uuid4
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from core.models import Person, PersonTitle, Title, PersonIdentifier, PersonGrouping, Grouping, PersonRelationship, \
    PersonPayment, GroupingRelationship
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from supporting.models import PersonIdentifierType, PersonGroupingType, PersonRelationshipType, GroupingRelationshipType
from django.test import tag, override_settings


class AtLeastSinceTestCase(FunctionalTestCase):

    def test_person_edit_page_doesnt_contain_as_of(self):
        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # And BTW there aren't any records in the system
        pass

        # When I go to the new officer edit page
        response_admin_client = admin_client.get('/changing/persons/add/person/', follow=True)
        # html = response_admin_client.content

        # Then I should see zero instances of the string "As of" in the page
        self.assertNotContains(
            response_admin_client,
            'As of',
        )

    def test_officer_profile_at_least_since_on_title(self):
        # Given there's a Title record associated with an officer where the start date is marked
        # at_least_since = True
        person = Person.objects.create(name='Test Person', is_law_enforcement=True)
        PersonTitle.objects.create(
            title=Title.objects.create(name='Test Title'),
            person=person,
            start_day=1,
            start_month=1,
            start_year=2001,
            at_least_since=True
        )

        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the officer profile page
        response_admin_client = admin_client.get(f'/officer/{person.pk}', follow=True)

        # Then the title should start with the phrase "at least since"
        # TODO: make this more narrow after merging html improvements into develop
        self.assertContains(
            response_admin_client,
            'at least since 01/01/2001',
        )
        # And "as of" should not be on the page
        self.assertNotContains(
            response_admin_client,
            'as of',
        )

    @skip('Depends on FDAB-117. Enable and double check after merging.')
    def test_officer_profile_at_least_since_on_person_relationship(self):
        # Given there's a PersonRelationship record associated with an officer where the start date is marked
        # at_least_since = True
        person = Person.objects.create(name='Test Person', is_law_enforcement=True)
        PersonRelationship.objects.create(
            subject_person=person,
            object_person=Person.objects.create(name='Test Person 2', is_law_enforcement=True),
            type=PersonRelationshipType.objects.create(name="Test Relationship Type"),
            start_day=1,
            start_month=1,
            start_year=2002,
            at_least_since=True
        )

        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the officer profile page
        response_admin_client = admin_client.get(f'/officer/{person.pk}', follow=True)

        # Then the relationship date should start with the phrase "at least since"
        # TODO: make this more narrow after merging html improvements into develop
        self.assertContains(
            response_admin_client,
            'at least since 01/01/2002',
        )
        # And "as of" should not be on the page
        self.assertNotContains(
            response_admin_client,
            'as of',
        )

    def test_officer_profile_at_least_since_on_person_payment(self):
        # Given there's a PersonPayment record associated with an officer where the start date is marked
        # at_least_since = True
        person = Person.objects.create(name='Test Person', is_law_enforcement=True)
        PersonPayment.objects.create(
            person=person,
            start_day=1,
            start_month=1,
            start_year=2003,
            at_least_since=True
        )

        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the officer profile page
        response_admin_client = admin_client.get(f'/officer/{person.pk}', follow=True)

        # Then the relationship date should start with the phrase "at least since"
        # TODO: make this more narrow after merging html improvements into develop
        self.assertContains(
            response_admin_client,
            'At least since 01/01/2003',
        )
        # And "as of" should not be on the page
        self.assertNotContains(
            response_admin_client,
            'as of',
        )

    def test_officer_profile_at_least_since_on_identifier(self):
        # Given there's an Identifier record associated with an officer where the start date is marked
        # at_least_since = True
        person = Person.objects.create(name='Test Person', is_law_enforcement=True)
        PersonIdentifier.objects.create(
            at_least_since=True,
            identifier='test identifier',
            person_identifier_type=PersonIdentifierType.objects.create(name='Test PersonIdentifierType'),
            person=person,
            start_day=1,
            start_month=1,
            start_year=2000
        )

        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the officer profile page
        response_admin_client = admin_client.get(f'/officer/{person.pk}', follow=True)

        # Then the identifier should start with the phrase "at least since"
        # TODO: make this more narrow after merging html improvements into develop
        self.assertContains(
            response_admin_client,
            'at least since 01/01/2000',
        )
        # And "as of" should not be on the page
        self.assertNotContains(
            response_admin_client,
            'as of',
        )

    def test_officer_profile_at_least_since_on_group(self):
        # Given there's a PersonGrouping record associated with an officer where the start date is marked
        # at_least_since = True
        person = Person.objects.create(name='Test Person', is_law_enforcement=True)
        PersonGrouping.objects.create(
            at_least_since=True,
            type=PersonGroupingType.objects.create(name='Test PersonGroupingType'),
            grouping=Grouping.objects.create(name='Test Grouping'),
            person=person,
            start_day=1,
            start_month=1,
            start_year=2002
        )

        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the officer profile page
        response_admin_client = admin_client.get(f'/officer/{person.pk}', follow=True)

        # Then the identifier should start with the phrase "at least since"
        # TODO: make this more narrow after merging html improvements into develop
        self.assertContains(
            response_admin_client,
            'at least since 01/01/2002',
        )
        # And "as of" should not be on the page
        self.assertNotContains(
            response_admin_client,
            'as of',
        )


class AtLeastSinceSeleniumTestCase(SeleniumFunctionalTestCase):
    """Use SeleniumFunctionalTestCase to launch a selenium driven Firefox browser to test the application.
    """

    @tag('wip')
    @override_settings(DEBUG=True)
    def test_at_least_since_edit_from_person_edit_page(self):
        b = self.browser
        # Given I'm logged into the system as an Admin
        self.log_in(is_administrator=True)

        with self.subTest('Titles "at least since"'):
            # and there's an existing Title type
            Title.objects.create(name='Test Title')

            # When I go to the new officer edit page
            self.browser.get(self.live_server_url + '/changing/persons/add/person/')

            # And on a new Title record I set the "at least since" field to checked
            self.browser.find_element(By.XPATH, "//*[text()=' Add another title']") \
                .click()
            wait(self.browser.find_element, By.CSS_SELECTOR, 'div.persontitleform') \
                .find_element(By.XPATH, ".//*[text()='At least since:']") \
                .click()
            # ... and other fields necessary fields
            Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
                .select_by_visible_text('Yes')
            b.find_element(By.CSS_SELECTOR, 'input[name="name"]')\
                .send_keys('verticillately woodchat')
            start_date_section = self.browser.find_element(By.CSS_SELECTOR, 'div#f_id_titles-0-person_title_started_0')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
                .send_keys('2000')
            Select(b.find_element(By.CSS_SELECTOR, 'div.persontitleform select.title')) \
                .select_by_visible_text('Test Title')
            b.find_element(By.CSS_SELECTOR, "input[value='Save']").click()

            # Then the title record's "at_least_since" field should be set to True
            self.assertEqual(
                True,
                PersonTitle.objects.get(person__name='verticillately woodchat').at_least_since
            )

        with self.subTest('Identifier "at least since"'):
            test_person_name = f"person-{uuid4()}"
            # and there's an existing PersonIdentifierType
            PersonIdentifierType.objects.create(name='Test PersonIdentifierType')

            # When I go to the new officer edit page
            self.browser.get(self.live_server_url + '/changing/persons/add/person/')

            # And on a new Identifier record I set the "at least since" field to checked
            self.browser.find_element(By.XPATH, "//*[text()=' Add another identifier']") \
                .click()
            wait(self.browser.find_element, By.CSS_SELECTOR, 'div.identifierform') \
                .find_element(By.XPATH, ".//*[text()='At least since:']") \
                .click()
            # ... and other necessary fields ...
            # ...   is_law_enforcement
            Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
                .select_by_visible_text('Yes')
            # ...   person name
            b.find_element(By.CSS_SELECTOR, 'input[name="name"]') \
                .send_keys(test_person_name)
            # ...   identifier value
            b.find_element(By.CSS_SELECTOR, '.identifierform input#id_identifiers-0-identifier') \
                .send_keys('Test Person Identifier')
            # ...   start date
            start_date_section = self.browser.find_element(
                By.CSS_SELECTOR, 'div#f_id_identifiers-0-identifier_started_0')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
                .send_keys('2000')
            # ...   type select
            Select(b.find_element(By.CSS_SELECTOR, 'div.identifierform select.personidentifiertype')) \
                .select_by_visible_text('Test PersonIdentifierType')
            # ...   and save
            b.find_element(By.CSS_SELECTOR, "input[value='Save']").click()

            # Then the identifier record's "at_least_since" field should be set to True
            self.assertEqual(
                True,
                PersonIdentifier.objects.get(person__name=test_person_name).at_least_since
            )

        with self.subTest('Group "at least since"'):
            test_person_name = f"person-{uuid4()}"
            # and there's an existing Grouping
            Grouping.objects.create(name='Test Grouping')

            # When I go to the new officer edit page
            self.browser.get(self.live_server_url + '/changing/persons/add/person/')

            # And on a new Group record I set the "at least since" field to checked
            self.browser.find_element(By.XPATH, "//*[text()=' Add another grouping']") \
                .click()
            wait(self.browser.find_element, By.CSS_SELECTOR, 'div.persongroupingform') \
                .find_element(By.XPATH, ".//*[text()='At least since:']") \
                .click()
            # ... and other necessary fields ...
            # ...   is_law_enforcement
            Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
                .select_by_visible_text('Yes')
            # ...   person name
            b.find_element(By.CSS_SELECTOR, 'input[name="name"]') \
                .send_keys(test_person_name)
            # ...   group
            self.enter_autocomplete_data(
                '.persongroupingform input#id_persongroupings-0-grouping_name',
                'ul.ui-autocomplete.groupingac li.ui-menu-item',
                'Test Grouping'
            )
            # ...   start date
            start_date_section = self.browser.find_element(
                By.CSS_SELECTOR, 'div#f_id_persongroupings-0-person_grouping_started_0')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
                .send_keys('2000')
            # ...   and save
            b.find_element(By.CSS_SELECTOR, "input[value='Save']").click()

            # Then the group record's "at_least_since" field should be set to True
            self.assertEqual(
                True,
                PersonGrouping.objects.get(person__name=test_person_name).at_least_since
            )

        with self.subTest('Payroll "at least since"'):
            test_person_name = f"person-{uuid4()}"

            # When I go to the new officer edit page
            self.browser.get(self.live_server_url + '/changing/persons/add/person/')

            # And on a new Payroll record I set the "at least since" field to checked
            self.browser.find_element(By.XPATH, "//*[text()=' Add another payroll']") \
                .click()
            wait(self.browser.find_element, By.CSS_SELECTOR, 'div.personpaymentform') \
                .find_element(By.CSS_SELECTOR, "#id_payments-0-at_least_since") \
                .click()
            # ... and other necessary fields ...
            # ...   is_law_enforcement
            Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
                .select_by_visible_text('Yes')
            # ...   person name
            b.find_element(By.CSS_SELECTOR, 'input[name="name"]') \
                .send_keys(test_person_name)
            # ...   and save
            b.find_element(By.CSS_SELECTOR, "input[value='Save']").click()

            # Then the payroll record's "at_least_since" field should be set to True
            self.assertEqual(
                True,
                PersonPayment.objects.get(person__name=test_person_name).at_least_since
            )


    @skip('Finish writing this after fixing FDAB-340')
    def test_at_least_since_edit_from_person_edit_page_person_releationship(self):
        # TODO: Finish writing this after fixing FDAB-340
        b = self.browser
        # Given I'm logged into the system as an Admin
        self.log_in(is_administrator=True)

        with self.subTest('PersonRelationship "at least since"'):
            test_person_name = f"person-{uuid4()}"
            # and there's an existing person
            other_person = Person.objects.create(name=f"person-{uuid4()}", is_law_enforcement=True)
            # and there's an existing PersonRelationshipType
            PersonRelationshipType.objects.create(name='testtype')

            # When I go to the new officer edit page
            self.browser.get(self.live_server_url + '/changing/persons/add/person/')

            # And on a new relationship record I set the "at least since" field to checked
            self.browser.find_element(By.XPATH, "//*[text()=' Add another relationship']") \
                .click()
            wait(self.browser.find_element, By.CSS_SELECTOR, 'div.personrelationshipform') \
                .find_element(By.XPATH, ".//*[text()='At least since:']") \
                .click()
            # ... and other necessary fields ...
            # ...   is_law_enforcement
            Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
                .select_by_visible_text('Yes')
            # ...   person name
            b.find_element(By.CSS_SELECTOR, 'input[name="name"]') \
                .send_keys(test_person_name)
            # ...   other person
            self.enter_autocomplete_data(
                '.personrelationshipform input#id_relationships-0-person_relationship_4',
                'ul.ui-autocomplete.personac li.ui-menu-item',
                other_person.name
            )
            # ...   relationship type
            self.browser.execute_script("arguments[0].scrollIntoView();", self.browser.find_element(By.CSS_SELECTOR, '.personrelationshipform select#id_relationships-0-person_relationship_2'))
            self.take_screenshot_and_dump_html()
            import pdb; pdb.set_trace()
            # TODO: Finish writing this after resolving FDAB-340
            self.browser.find_element(By.CSS_SELECTOR,
                                      '.personrelationshipform select#id_relationships-0-person_relationship_2') \
                .select_by_visible_text('testtype')
            # ...   start date
            start_date_section = self.browser.find_element(
                By.CSS_SELECTOR, 'div#f_id_relationships-0-person_relationship_started_0')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.datemonth') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateday') \
                .send_keys('1')
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear').clear()
            start_date_section.find_element(By.CSS_SELECTOR, 'input.dateyear') \
                .send_keys('2000')
            # ...   and save
            b.find_element(By.CSS_SELECTOR, "input[value='Save']").click()


            # Then the relationship record's "at_least_since" field should be set to True
            self.assertEqual(
                True,
                PersonRelationship.objects.get(subject_person__name=test_person_name).at_least_since
            )
