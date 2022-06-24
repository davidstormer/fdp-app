from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from core.models import (
    Grouping,
    Person
)
from functional_tests.common import (
    SeleniumFunctionalTestCase,
    wait
)
from supporting.models import Title


class GroupingOnPersonTitleSeleniumTestCase(SeleniumFunctionalTestCase):
    def test_grouping_on_person_title(self):
        """Test that I can fill out the grouping field on a person title on the person changing page, and that
        it's displayed on the officer profile page after I save it.
        """
        b = self.browser
        self.log_in(is_administrator=True)

        # ... add an existing Title type
        Title.objects.create(name='Test Title')
        # ... add an existing Grouping
        Grouping.objects.create(name='monoxenous')

        self.browser.get(self.live_server_url + '/changing/persons/add/person/')

        self.browser.find_element(By.XPATH, "//*[text()=' Add another title']") \
            .click()

        # When I set the Grouping to an existing group
        #
        #
        self.enter_autocomplete_data(
            '.persontitleform input#id_titles-0-grouping_name',
            'ul.ui-autocomplete.titlegroupingac li.ui-menu-item',
            'monoxenous'
        )

        # .. fill out other necessary fields
        Select(b.find_element(By.CSS_SELECTOR, 'select#id_law_enforcement')) \
            .select_by_visible_text('Yes')
        b.find_element(By.CSS_SELECTOR, 'input[name="name"]')\
            .send_keys('Kidderminster')
        Select(b.find_element(By.CSS_SELECTOR, 'div.persontitleform select.title')) \
            .select_by_visible_text('Test Title')

        # ...   and save
        b.find_element(By.CSS_SELECTOR, "input[value='Save']").click()

        # Then I should see the grouping shown under the title on the new officer profile page
        #
        #
        self.browser.get(self.live_server_url + f'/officer/{Person.objects.last().pk}')
        self.assertIn(
            'monoxenous',
            self.el('section.identification').text
        )
