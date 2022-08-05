from unittest import skip
from functional_tests.common import wait, SeleniumFunctionalTestCase, FunctionalTestCase
from django.test import override_settings


class MyNonSeleniumTestCase(FunctionalTestCase):
    """Use FunctionalTestCase as a lightweight alternative to SeleniumFunctionalTestCase when JavaScript and styling
    do not need to be accounted for.
    """

    def test_page_exists(self):
        # Given I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        response_admin_client = admin_client.get('/bootstrap-style-guide', follow=True)
        self.assertContains(
            response_admin_client,
            "Typography"
        )
#
#
# class BootstrapBase(SeleniumFunctionalTestCase):
#     def test_page_exists(self):
#         # Given I'm logged into the system as an Admin
#         self.log_in(is_administrator=True)
#         self.browser.get(self.live_server_url + '/bootstrap-style-guide')
#         heading = wait(self.browser.find_element_by_css_selector, 'article#typography h3')
#         self.assertEqual(
#             "Typography",
#             heading.text
#         )
