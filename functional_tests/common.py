import pdb
from django.test import Client
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select

from fdpuser.models import FdpUser
from inheritable.tests import AbstractTestCase
from lxml.html.soupparser import fromstring
import os
from datetime import datetime
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException, NoSuchElementException
import time
from django.utils.timezone import now
from django_otp.oath import totp
from django_otp.util import random_hex
from django_otp.plugins.otp_totp.models import TOTPDevice
from uuid import uuid4

SCREEN_DUMP_LOCATION = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'screendumps'
)


def setup_user(is_host: bool = True,
                is_administrator: bool = False,
                is_superuser: bool = False,
                username: str = 'user@localhost',
                password: str = 'opensesame'):
    user = FdpUser.objects.create_user(
        username,
        password,
        is_host=is_host,
        is_administrator=is_administrator,
        is_superuser=is_superuser)
    # add agreement to EULA, so splash page does not interrupt tests
    user.agreed_to_eula = now()
    user.full_clean()
    user.save()
    # Set up totp
    key = random_hex()
    user.totpdevice_set.create(name='default', key=key)
    return user


def wait(fn, *args, **kwargs):
    """Call a given function repeatedly until it doesn't raise AssertionError or WebDriverException.
    Gives up after a few tries.
    """
    max_tries = 20

    start_time = time.time()
    while True:
        try:
            return fn(*args, **kwargs)
        except (AssertionError, WebDriverException, NoSuchElementException) as e:
            if time.time() - start_time > max_tries:
                print(f"Tried {max_tries} times. Raising exception...")
                raise e
            time.sleep(0.5)


class FunctionalTestCase(AbstractTestCase):
    def log_in(self, is_host=True, is_administrator=False, is_superuser=False) -> object:
        """Log into the system
        - Create an account
        - Set the password
        - Set up 2FA tokens
        - Log into the system

        Returns a Django test client object
        """
        client = Client()
        fdp_user = self._create_fdp_user(
            password=self._password,
            is_host=is_host,
            is_administrator=is_administrator,
            is_superuser=is_superuser,
            email_counter=FdpUser.objects.all().count()
        )
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        login_response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        return client

    def log_in_as(self, email, is_host=True, is_administrator=False, is_superuser=False) -> object:
        """Log into the system
        - Create an account
        - Set the password
        - Set up 2FA tokens
        - Log into the system

        Returns a Django test client object
        """
        client = Client()
        fdp_user = self._create_fdp_user(
            password=self._password,
            is_host=is_host,
            is_administrator=is_administrator,
            is_superuser=is_superuser,
            email_counter=FdpUser.objects.all().count(),
            email=email
        )
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        login_response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        return client

    @staticmethod
    def get_element_text(document_html: str, cssselector: str, nth_element: int = 0) -> str:
        """Parse given html using beautiful soup, then find given element using CSS style selectors, then finally get
        the text contents of the element and the text of its children concatenated.
        Whereas lxml's stock parser is too strict, this method uses beautiful soup to parse potentially messy HTML.
        Whereas lxml's stock behavior requires xpath queries, this method uses easier CSS style selector syntax.
        Whereas lxml's .text property only returns the text within an element, this method returns the text of its
        children too.
        """
        document = fromstring(document_html)
        return ' '.join(document.cssselect(cssselector)[nth_element].itertext())


class SeleniumFunctionalTestCase(StaticLiveServerTestCase):

    def setUp(self):
        try:
            self.browser = webdriver.Firefox()
        except (SessionNotCreatedException, WebDriverException) as e:
            self.skipTest(f"WARNING skipping test, couldn't start Selenium web driver -- {e}")

    def tearDown(self):
        if self._test_has_failed():
            self.take_screenshot_and_dump_html()
        self.browser.quit()
        super().tearDown()

    def _test_has_failed(self):
        # slightly obscure but couldn't find a better way!
        return any(error for (method, error) in self._outcome.errors)

    def take_screenshot_and_dump_html(self, msg=''):
        if not os.path.exists(SCREEN_DUMP_LOCATION):
            os.makedirs(SCREEN_DUMP_LOCATION)
        for ix, handle in enumerate(self.browser.window_handles):
            self._windowid = ix
            self.browser.switch_to.window(handle)
            filename = self._get_filename() + msg + '.png'
            print('screenshotting to', filename)
            self.browser.get_screenshot_as_file(filename)
            filename = self._get_filename() + '.html'
            print('dumping page HTML to', filename)
            with open(filename, 'w') as f:
                f.write(self.browser.page_source)

    def _get_filename(self):
        timestamp = datetime.now().isoformat().replace(':', '.')[:19]
        return '{folder}/{classname}.{method}-window{windowid}-{timestamp}'.format(
            folder=SCREEN_DUMP_LOCATION,
            classname=self.__class__.__name__,
            method=self._testMethodName,
            windowid=self._windowid,
            timestamp=timestamp
        )

    def log_in(self, is_host=True, is_administrator=False, is_superuser=False) -> FdpUser:
        """Log into the system
        - Create an account
        - Set the password
        - Set up 2FA tokens
        - Log into the system

        Returns a Django test client object
        """
        b = self.browser
        # create user
        user = setup_user(
            username=f"user-{uuid4()}@example.com",
            password='opensesame',
            is_host=is_host,
            is_administrator=is_administrator,
            is_superuser=is_superuser
        )
        # log user in
        b.get(self.live_server_url)
        b.find_element_by_name('auth-username') \
         .send_keys(user.email)
        b.find_element_by_name('auth-password') \
         .send_keys('opensesame')
        b.find_element_by_css_selector('button') \
         .click()
        # succeed 2fa challenge
        totp_device = TOTPDevice.objects.get(user=user)
        otp = totp(totp_device.bin_key)
        wait(b.find_element_by_name, 'token-otp_token') \
            .send_keys(otp)
        b.find_element_by_css_selector('button') \
         .click()
        # confirm that we're logged in
        wait(b.find_element_by_css_selector, 'div#user-tools a.onlogout')
        # all done
        return user

    def log_out(self):
        self.browser.get(self.live_server_url + '/account/logout/')

    def enter_autocomplete_data(self, input_css_selector: str, results_css_selector: str, search_string: str,
                                nth_result: int = 1) -> None:
        """Interacts with the autocomplete widget to select a database entity.

        :param input_css_selector: E.g. '.persongroupingform input#id_persongroupings-0-grouping_name'
        :param results_css_selector: E.g. 'ul.ui-autocomplete.groupingac li.ui-menu-item'
        :param search_string: E.g. 'Test Grouping'
        :param nth_result: How many down the list to select, defaults to 1
        """
        group_input = self.browser.find_element(By.CSS_SELECTOR, input_css_selector)
        group_input.send_keys(search_string)
        # wait for search results to be returned
        wait(self.browser.find_element, By.CSS_SELECTOR, results_css_selector)
        # then select it
        for i in range(nth_result):
            group_input.send_keys(Keys.DOWN)
        group_input.send_keys(Keys.ENTER)

    def select2_select_by_visible_text(self, field_name: str, option_to_select_text: str):
        select2_input = self.el(f'div#div_{field_name} input.select2-search__field')
        ActionChains(self.browser).move_to_element(select2_input).click().perform()
        options = self.el(f'ul#select2-{field_name}-results')
        option_to_select = options.find_element(By.XPATH, f'//li[contains(text(), "{option_to_select_text}")]')
        self.browser.execute_script("arguments[0].scrollIntoView();", option_to_select)
        ActionChains(self.browser).move_to_element(option_to_select).click().perform()
        if option_to_select_text not in self.el(f"div#div_{field_name} .select2-selection__rendered").text:
            raise Exception(f"Failed to select '{option_to_select_text}' in Select2 select dropdown '{field_name}'")

    def wait_for(self, css_selector: str) -> WebElement:
        """Block until element found by given css selector"""
        wait(self.browser.find_element, By.CSS_SELECTOR, css_selector)

    def el(self, css_selector: str) -> WebElement:
        """Shorthand for wait(self.browser.find_element, By.CSS_SELECTOR, css_selector)"""
        return wait(self.browser.find_element, By.CSS_SELECTOR, css_selector)

    def select_list(self, name: str) -> Select:
        return Select(wait(self.browser.find_element, By.CSS_SELECTOR, f'select[name="{name}"]'))

    def input(self, name: str) -> WebElement:
        return wait(self.browser.find_element, By.CSS_SELECTOR, f'input[name="{name}"]')

    def submit_button(self, value: str) -> WebElement:
        return wait(self.browser.find_element, By.CSS_SELECTOR, f"input[value='{value}']")

    def submit_button_el(self, value: str) -> WebElement:
        return wait(self.browser.find_element, By.XPATH, f'//button[text()="{value}"]')

    def wait_for(self, css_selector: str):
        """Pause execution until the given element is found
        """
        self.el(css_selector)
