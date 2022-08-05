from functional_tests.common import SeleniumFunctionalTestCase, wait
from django.test import override_settings


class SessionTimeoutPopup(SeleniumFunctionalTestCase):
    # GIVEN the session is set to three seconds
    @override_settings(SESSION_COOKIE_AGE=3)
    def test_session_timed_out(self):
        pages_to_check = [
            '/',
            '/admin/',
            '/bootstrap-style-guide',
        ]

        def popup_has_message():
            popup = self.browser.find_element_by_css_selector('p#sessionexpirymsg')
            # THEN I should see a message about my session being expired
            self.assertIn(
                "Your session has expired. Please log in again.",
                popup.text
            )
        for path in pages_to_check:
            with self.subTest(path=path):
                # GIVEN I'm logged into the system as an Admin
                self.browser.get(self.live_server_url + '/account/logout/')
                self.log_in(is_administrator=True)
                # and GIVEN I'm on one of the given pages
                self.browser.get(self.live_server_url + path)
                # WHEN I wait for five seconds
                wait(popup_has_message)
                if path == '/bootstrap-style-guide':
                    self.take_screenshot_and_dump_html()
