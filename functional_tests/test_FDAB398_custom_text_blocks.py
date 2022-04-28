import pdb
from time import sleep

from django.db import transaction
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from core.models import Person, Grouping, PersonGrouping, Incident, PersonIncident, GroupingIncident
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from profiles.models import SiteSetting, SiteSettingKeys


class CustomTextBlocksSelenium(SeleniumFunctionalTestCase):
    def test_custom_text_blocks_success_scenario(self):
        person_record = Person.objects.create(name='Test officer', is_law_enforcement=True)
        command_record = Grouping.objects.create(name="Test command", is_law_enforcement=True)
        PersonGrouping.objects.create(grouping=command_record, person=person_record)
        incident_record = Incident.objects.create(description="Test Incident")
        PersonIncident.objects.create(person=person_record, incident=incident_record)
        GroupingIncident.objects.create(grouping=command_record, incident=incident_record)

        cases = [
            {
                "msg": "Officer profile page top",
                "given_text_block_input": "#id_profile_page_top",
                "when_path": reverse('profiles:officer', kwargs={'pk': person_record.pk}),
                "then_element": 'div#custom-header-text',
            },
            {
                "msg": "Officer profile above incidents",
                "given_text_block_input": "#id_profile_incidents",
                "when_path": reverse('profiles:officer', kwargs={'pk': person_record.pk}),
                "then_element": 'div#custom-text-block-incidents',
            },
            {
                "msg": "Command profile page top",
                "given_text_block_input": "#id_profile_page_top",
                "when_path": reverse('profiles:command', kwargs={'pk': command_record.pk}),
                "then_element": 'div#custom-header-text',
            },
            {
                "msg": "Command profile above incidents",
                "given_text_block_input": "#id_profile_incidents",
                "when_path": reverse('profiles:command', kwargs={'pk': command_record.pk}),
                "then_element": 'div#custom-text-block-incidents',
            },
            {
                "msg": "Global footer left on profile",
                "given_text_block_input": '#id_global_footer_left',
                "when_path": reverse('profiles:officer', kwargs={'pk': person_record.pk}),
                "then_element": 'div#custom-text-block-global-left',
            },
            {
                "msg": "Global footer left bootstrap style guide",
                "given_text_block_input": '#id_global_footer_left',
                "when_path": '/bootstrap-style-guide',
                "then_element": 'div#custom-text-block-global-left',
            },
            {
                "msg": "Global footer right bootstrap style guide",
                "given_text_block_input": '#id_global_footer_right',
                "when_path": '/bootstrap-style-guide',
                "then_element": 'div#custom-text-block-global-right',
            },
        ]

        # Given I'm on the site settings page and there's an officer record
        self.log_in(is_administrator=True)

        for case in cases:
            with self.subTest(msg=case['msg']):
                with transaction.atomic():  # Maintain test isolation
                    self.browser.get(self.live_server_url + '/admin/site-settings')

                    # When I enter text in the given field and save
                    text_area = wait(self.browser.find_element_by_css_selector, case['given_text_block_input'])
                    wait(text_area.clear)
                    text_area.send_keys(f"{case['msg']} rollerskating precisionist")
                    self.browser.find_element_by_css_selector("input[type='submit'][value='Save']") \
                        .submit()

                    # Then I should see the text in the given output element
                    sleep(1)  # Couldn't get around this, sorry...
                    self.browser.get(self.live_server_url + case['when_path'])
                    text_block = wait(self.browser.find_element_by_css_selector, case['then_element'])
                    self.assertEqual(
                        f"{case['msg']} rollerskating precisionist",
                        text_block.text,
                        msg='Custom text block missing'
                    )
                    transaction.set_rollback(True)  # ... maintain test isolation

    def test_global(self):

        # Given I'm on the site settings page and there's an officer record
        self.log_in(is_administrator=True)
        self.browser.get(self.live_server_url + '/admin/site-settings')
        person_record = Person.objects.create(name='Test officer', is_law_enforcement=True)

        # When I enter text in the "Global footer" field and save
        wait(self.browser.find_element_by_css_selector, '#id_global_footer_left') \
            .send_keys('plenteous continuum')
        self.browser.find_element_by_css_selector("input[type='submit'][value='Save']") \
            .submit()

        # Then I should see a text box at the bottom of the officer profile page
        self.browser.get(self.live_server_url + reverse('profiles:officer', kwargs={'pk': person_record.pk}))
        text_block = wait(self.browser.find_element_by_css_selector, 'div#custom-text-block-global-left')
        self.assertEqual(
            'plenteous continuum',
            text_block.text
        )

        # And the home page
        self.browser.get(self.live_server_url + '/')
        text_block = wait(self.browser.find_element_by_css_selector, 'div#custom-text-block-global-left')
        self.assertEqual(
            'plenteous continuum',
            text_block.text
        )

        with self.subTest(msg="But not the admin 'changing' pages"):
            # But not the admin 'changing' pages
            self.browser.get(self.live_server_url + reverse('changing:index'))
            self.assertNotIn(
                'plenteous continuum',
                self.browser.page_source
            )

        with self.subTest(msg="But not the django admin pages"):
            # And not the django admin pages
            self.browser.get(self.live_server_url + reverse('admin:index'))
            self.assertNotIn(
                'plenteous continuum',
                self.browser.page_source
            )

    def test_site_settings_page_exists(self):
        # Given I'm logged in as an admin
        self.log_in(is_administrator=True)

        # When I go to the admin landing page
        self.browser.get(self.live_server_url + reverse('changing:index'))

        # Then I should see a "site settings" option
        link = self.browser.find_element(By.LINK_TEXT, 'Site Settings')

        # When I click it
        link.click()

        # Then I should be taken to a 'site settings' page
        h1 = self.browser.find_element(By.CSS_SELECTOR, 'h1')
        self.assertEqual(
            'Site settings',
            h1.text
        )

    def test_html_sanitization(self):
        person_record = Person.objects.create(name='Test officer', is_law_enforcement=True)
        command_record = Grouping.objects.create(name="Test command", is_law_enforcement=True)
        PersonGrouping.objects.create(grouping=command_record, person=person_record)
        incident_record = Incident.objects.create(description="Test Incident")
        PersonIncident.objects.create(person=person_record, incident=incident_record)
        GroupingIncident.objects.create(grouping=command_record, incident=incident_record)

        cases = [
            {
                "msg": "Profile page top",
                "given_text_block_input": "#id_profile_page_top",
                "when_path": reverse('profiles:officer', kwargs={'pk': person_record.pk}),
                "then_element": 'div#custom-header-text',
             },
            {
                "msg": "Profile above incidents",
                "given_text_block_input": "#id_profile_incidents",
                "when_path": reverse('profiles:officer', kwargs={'pk': person_record.pk}),
                "then_element": 'div#custom-text-block-incidents',
            },
            {
                "msg": "Global left on profile",
                "given_text_block_input": '#id_global_footer_left',
                "when_path": reverse('profiles:officer', kwargs={'pk': person_record.pk}),
                "then_element": 'div#custom-text-block-global-left',
            },
            {
                "msg": "Global left bootstrap style guide",
                "given_text_block_input": '#id_global_footer_left',
                "when_path": '/bootstrap-style-guide',
                "then_element": 'div#custom-text-block-global-left',
            },
            {
                "msg": "Global right on profile",
                "given_text_block_input": '#id_global_footer_right',
                "when_path": reverse('profiles:officer', kwargs={'pk': person_record.pk}),
                "then_element": 'div#custom-text-block-global-right',
            },
            {
                "msg": "Global right bootstrap style guide",
                "given_text_block_input": '#id_global_footer_right',
                "when_path": '/bootstrap-style-guide',
                "then_element": 'div#custom-text-block-global-right',
            },
        ]

        # Given I'm on the site settings page and there's an officer record
        self.log_in(is_administrator=True)

        for case in cases:
            with self.subTest(msg=case['msg']):
                    self.browser.get(self.live_server_url + '/admin/site-settings')

                    # When I enter text in the given field and save
                    text_area = wait(self.browser.find_element_by_css_selector, case['given_text_block_input'])
                    wait(text_area.clear)
                    text_area.send_keys(f"{case['msg']} <b>mandrel</b> <marquee>lancaster</marquee>")
                    self.browser.find_element_by_css_selector("input[type='submit'][value='Save']") \
                        .submit()

                    # Then I should see the text in the given output element
                    def then_():
                        self.browser.get(self.live_server_url + case['when_path'])
                        text_block = wait(self.browser.find_element_by_css_selector, case['then_element'])
                        self.assertEqual(
                            f"{case['msg']} mandrel <marquee>lancaster</marquee>",
                            text_block.text,
                            msg='Disallowed HTML not being escaped!'
                        )

                    wait(then_)
