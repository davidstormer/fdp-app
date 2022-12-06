from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from core.models import Grouping, Person, Incident
from functional_tests.common import SeleniumFunctionalTestCase
from django.test import tag

from sourcing.models import Attachment, Content
from supporting.models import Title, AttachmentType


class LegacyLookUpToolsTestCase(SeleniumFunctionalTestCase):

    def test_person_edit_page_groupings(self):
        # Given there's an existing grouping record
        grouping_record = Grouping.objects.create(name="Test Grouping plumless")
        # And I'm on an officer edit page
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')
        # And I've clicked 'Add another grouping'
        self.browser.find_element(By.XPATH, "//*[text()=' Add another grouping']") \
            .click()

        # When I enter a matching search string
        search_input = self.el('.persongroupingform input#id_persongroupings-0-grouping_name')
        search_input.send_keys('plumless')

        # Then I should see the grouping appear in the list
        results_listing = self.el('ul.ui-autocomplete.groupingac li.ui-menu-item')
        self.assertIn(
            grouping_record.name,
            results_listing.text
        )

        # And when I click on it
        options = self.el(f'ul.ui-autocomplete.groupingac')
        option_to_select = options.find_element(By.XPATH, f'//div[contains(text(), "{grouping_record.name}")]')
        self.browser.execute_script("arguments[0].scrollIntoView();", option_to_select)
        ActionChains(self.browser).move_to_element(option_to_select).click().perform()

        # Then I should see the name in the input field now
        self.assertEqual(
            search_input.get_attribute("value"),
            grouping_record.name
        )

        # And when I save the record
        # ...   is_law_enforcement
        Select(self.el('select#id_law_enforcement')) \
            .select_by_visible_text('Yes')
        # ...   person name
        self.el('input[name="name"]') \
            .send_keys('Test Person histopathologist')
        # ... click save
        self.submit_button('Save').click()

        # And when I go to the officer profile page
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')
        # Then I should see the grouping listed in the identification section
        self.assertIn(
            grouping_record.name,
            self.el('ul#commands').text
        )

    def test_person_edit_page_titles(self):
        # Given there's an existing grouping record
        grouping_record = Grouping.objects.create(name="Test Grouping plumless")
        # And a title record
        Title.objects.create(name="Test Title")

        # And I'm on an officer edit page
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/persons/add/person/')

        self.browser.find_element(By.XPATH, "//*[text()=' Add another title']") \
            .click()
        Select(self.el('div.persontitleform select.title')) \
            .select_by_visible_text('Test Title')

        # When I enter a matching search string
        search_input = self.el('.persontitleform input#id_titles-0-grouping_name')
        search_input.send_keys('plumless')

        # Then I should see the grouping appear in the list
        results_listing = self.el('ul.ui-autocomplete.titlegroupingac li.ui-menu-item')
        self.assertIn(
            grouping_record.name,
            results_listing.text
        )

        # And when I click on it
        options = self.el(f'ul.ui-autocomplete.titlegroupingac')
        option_to_select = options.find_element(By.XPATH, f'//div[contains(text(), "{grouping_record.name}")]')
        self.browser.execute_script("arguments[0].scrollIntoView();", option_to_select)
        ActionChains(self.browser).move_to_element(option_to_select).click().perform()

        # Then I should see the name in the input field now
        self.assertEqual(
            search_input.get_attribute("value"),
            grouping_record.name
        )

        # And when I save the record
        # ...   is_law_enforcement
        Select(self.el('select#id_law_enforcement')) \
            .select_by_visible_text('Yes')
        # ...   person name
        self.el('input[name="name"]') \
            .send_keys('Test Person histopathologist')
        # ... click save
        self.submit_button('Save').click()

        # And when I go to the officer profile page
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')
        # Then I should see the grouping listed in the identification section
        self.assertIn(
            grouping_record.name,
            self.el('ul.titles').text
        )

    def test_incident_edit_page_groupings(self):
        grouping_record = Grouping.objects.create(name="Test Grouping plumless")

        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/incidents/add/incident/')

        self.browser.find_element(By.XPATH, "//*[text()=' Add another grouping']") \
            .click()

        search_input = self.el('.groupingincidentform #id_groupingincidents-0-grouping_name')
        search_input.send_keys('plumless')

        results_listing = self.el('ul.ui-autocomplete.groupingac li.ui-menu-item')
        self.assertIn(
            grouping_record.name,
            results_listing.text
        )

        options = self.el(f'ul.ui-autocomplete.groupingac')
        option_to_select = options.find_element(By.XPATH, f'//div[contains(text(), "{grouping_record.name}")]')
        self.browser.execute_script("arguments[0].scrollIntoView();", option_to_select)
        ActionChains(self.browser).move_to_element(option_to_select).click().perform()

        self.assertEqual(
            search_input.get_attribute("value"),
            grouping_record.name
        )

        self.submit_button('Save').click()

        self.browser.get(self.live_server_url + f'/changing/incidents/update/incident/{Incident.objects.last().pk}/0/')

        search_input = self.el('.groupingincidentform #id_groupingincidents-0-grouping_name')
        self.assertEqual(
            search_input.get_attribute("value"),
            grouping_record.name
        )

    def test_content_attachments(self):
        attachment_record = Attachment.objects.create(
            name='Test Attachment faciolingual',
            type=AttachmentType.objects.create(name='Test Attachment Type')
        )

        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/content/add/content/')

        self.browser.find_element(By.XPATH, "//*[text()=' Add another attachment']") \
            .click()

        search_input = self.el('.attachmentform input#id_attachments-0-attachment_name')
        search_input.send_keys('faciolingual')

        results_listing = self.el('ul.ui-autocomplete.attachmentac li.ui-menu-item')
        self.assertIn(
            attachment_record.name,
            results_listing.text
        )

        options = self.el(f'ul.ui-autocomplete.attachmentac')
        option_to_select = options.find_element(By.XPATH, f'//div[contains(text(), "{attachment_record.name}")]')
        self.browser.execute_script("arguments[0].scrollIntoView();", option_to_select)
        ActionChains(self.browser).move_to_element(option_to_select).click().perform()

        self.assertEqual(
            search_input.get_attribute("value"),
            attachment_record.name
        )

        self.submit_button('Save').click()

        self.browser.get(self.live_server_url + f'/changing/content/update/content/{Content.objects.last().pk}')

        search_input = self.el('.attachmentform input#id_attachments-0-attachment_name')
        self.assertEqual(
            search_input.get_attribute("value"),
            attachment_record.name
        )

    @tag('wip')
    def test_content_incidents(self):
        incident_record = Incident.objects.create(description="Test Incident villakin")

        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/changing/content/add/content/')

        self.browser.find_element(By.XPATH, "//*[text()=' Add another incident']") \
            .click()

        search_input = self.el('.incidentform input#id_incidents-0-incident_name')
        search_input.send_keys('villakin')

        results_listing = self.el('ul.ui-autocomplete.incidentac li.ui-menu-item')
        self.assertIn(
            incident_record.description,
            results_listing.text
        )

        options = self.el(f'ul.ui-autocomplete.incidentac')
        option_to_select = options.find_element(By.XPATH, f'//div[contains(text(), "{incident_record.description}")]')
        self.browser.execute_script("arguments[0].scrollIntoView();", option_to_select)
        ActionChains(self.browser).move_to_element(option_to_select).click().perform()

        self.assertEqual(
            search_input.get_attribute("value"),
            incident_record.description
        )

        self.submit_button('Save').click()

        self.browser.get(self.live_server_url + f'/changing/content/update/content/{Content.objects.last().pk}')

        search_input = self.el('.incidentform input#id_incidents-0-incident_name')
        self.assertEqual(
            search_input.get_attribute("value"),
            incident_record.description
        )
