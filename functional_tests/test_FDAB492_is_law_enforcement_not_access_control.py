from selenium.webdriver.common.by import By

from core.models import Person
from functional_tests.common import SeleniumFunctionalTestCase, wait
import re
from django.test import tag, override_settings


class IsLawEnforcementNotAccessControl(SeleniumFunctionalTestCase):
    @tag('wip')
    def test_is_law_enforcement_not_access_control_success_scenario(self):
        # Given there's a Person record where is_law_enforcement=False
        person_record = Person.objects.create(
            is_law_enforcement=False,
            name="Test Civilian pyrosphere"
        )

        # Given I'm a staff user
        self.log_in(is_administrator=False)

        # When I go to the search page
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        self.el('input[name="q"]') \
            .send_keys("pyrosphere")
        self.el("input[value='Search']") \
            .click()

        self.assertIn(
            "pyrosphere",
            self.el("div.search-results li.row-1").text
        )

        # When I go to the profile page
        self.el("div.search-results li.row-1 a.profile-link") \
            .click()

        # Then I should not see a 404 error message
        self.assertNotRegex(
            self.el('body').text,
            re.compile('NOT FOUND', re.IGNORECASE)
        )

        # Then I should see a heading titled...
        self.assertIn(
            'Test Civilian pyrosphere',
            self.el("#content h1").text
        )
