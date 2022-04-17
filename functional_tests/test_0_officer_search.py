from unittest import skip

from selenium.webdriver.common.by import By

from core.models import Person
from functional_tests.common import wait, SeleniumFunctionalTestCase


class MySeleniumTestCase(SeleniumFunctionalTestCase):
    pass
    # I couldn't reproduce the problem this way!
    # def test_bug_middle_names_issue(self):
    #     # Given there are two "Roger Hobbes" records with one containing a middle initial
    #     Person.objects.create(name="Roger Hobbes", is_law_enforcement=True)
    #     Person.objects.create(name="Roger E. Hobbes", is_law_enforcement=True)
    #     # and there are six other officer records that start with "Roger"
    #     officer_names = [
    #         'Roger Bugaboo',
    #         'Roger Incrementally',
    #         'Roger Arturo',
    #         'Roger Confronters',
    #         'Roger Underlying',
    #         'Roger Acclimates',
    #     ]
    #     for officer_name in officer_names:
    #         Person.objects.create(name=officer_name, is_law_enforcement=True)
    #
    #     # When I do a search for "Roger Hobbes"
    #     self.log_in(is_administrator=True)
    #     self.browser.get(self.live_server_url + '/officer/search/')
    #     wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="search"]') \
    #         .send_keys("Roger Hobbes")
    #     self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']").click()
    #
    #     # Then the record with the middle initial is not the second or third result
    #     self.take_screenshot_and_dump_html()
    #     import pdb; pdb.set_trace()
