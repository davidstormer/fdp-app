from django.test import TestCase
from core.models import Person
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from inheritable.tests import local_test_settings_required
from unittest import expectedFailure, skip
from selenium.webdriver.support.ui import Select
import pdb


class MyNonSeleniumTestCase(FunctionalTestCase):
    """Use FunctionalTestCase as a lightweight alternative to SeleniumFunctionalTestCase when JavaScript and styling
    do not need to be accounted for.
    """

    def test_demo_person_record(self):
        Person.objects.create(name="Hello World")
        people = Person.objects.all()
        self.assertEqual(
            1,
            len(people)
        )

    def test_demo_login(self):
        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the root of the site '/'
        response_admin_client = admin_client.get('/', follow=True)
        html = response_admin_client.content

        # Then I should see an h1 that reads "What are you searching for?"
        second_h1_contents = self.get_element_text(html, 'h1', nth_element=1)
        self.assertEqual(
            "What are you searching for?",
            second_h1_contents
        )
        # ... btw:
        first_h1_contents = self.get_element_text(html, 'h1')
        self.assertEqual(
            "Full Disclosure Project",
            first_h1_contents
        )


class MySeleniumTestCase(SeleniumFunctionalTestCase):
    """Use SeleniumFunctionalTestCase to launch a selenium driven Firefox browser to test the application.
    """

    # Simple example
    def test_demo_login_page(self):
        self.browser.get(self.live_server_url)
        button = self.browser.find_element_by_css_selector('button')
        # More methods here: https://selenium-python.readthedocs.io/locating-elements.html
        self.assertIn(
            'Log in',
            button.text
        )

    # But what if something fails? Comment out @expectedFailure to see!
    @expectedFailure
    def test_demo_broken_test(self):
        self.browser.get(self.live_server_url)
        self.assertIn(
            'coo coo banana pants',
            self.browser.page_source
        )
        # ... dumps a screenshot and the html output into a screendumps directory.

    # And how do I log in?
    def test_demo_logging_in(self):
        # Given I'm logged into the system as an Admin
        self.log_in(is_administrator=True)
        heading = wait(self.browser.find_element_by_css_selector, 'div#content h1')
        self.assertEqual(
            "What are you searching for?",
            heading.text
        )
