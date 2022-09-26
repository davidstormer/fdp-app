from django.db import transaction
from selenium.webdriver.common.by import By
from core.models import Person
from fdpuser.models import FdpOrganization
from functional_tests.common import wait, SeleniumFunctionalTestCase


class OrganizationAccessControls(SeleniumFunctionalTestCase):
    def test_person_hidden_when_org_set_and_non_host_user_not_in_org(self):
        # Given there is an officer record named "Miesha Britton"
        person = Person.objects.create(name="Miesha Britton", is_law_enforcement=True)
        # Given there's an FDP Organization access control on it
        fdp_organization = FdpOrganization.objects.create(name='Test Organization')
        person.fdp_organizations.add(fdp_organization)

        # Given I'm not in the FDP Organization
        self.log_in(is_administrator=False)

        # When I do a search for "Miesha Britton"
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Miesha Britton")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then the page should say "No results found"
        self.assertIn(
            'No results found',
            self.el('.search-results').text
        )

        with self.subTest(msg="Officer links"):
            # When I go to the officer profile page
            self.browser.get(f'{self.live_server_url}/officer/{person.pk}')

            # Then I should get a 404 error
            self.assertIn(
                "Not Found",
                self.el("h1").text
            )

    def test_person_hidden_when_org_set_and_host_user_not_in_org(self):
        # Given there is an officer record named "Miesha Britton"
        person = Person.objects.create(name="Miesha Britton", is_law_enforcement=True)
        # Given there's an FDP Organization access control on it
        fdp_organization = FdpOrganization.objects.create(name='Test Organization')
        person.fdp_organizations.add(fdp_organization)

        # Given I'm not in the FDP Organization
        # But I am a host user
        self.log_in(
            is_administrator=False,
            is_host=True  # <- This
        )

        # When I do a search for "Miesha Britton"
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Miesha Britton")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then the page should say "No results found"
        self.assertIn(
            'No results found',
            self.el('.search-results').text
        )

        with self.subTest(msg="Officer links"):
            # When I go to the officer profile page
            self.browser.get(f'{self.live_server_url}/officer/{person.pk}')

            # Then I should get a 404 error
            self.assertIn(
                "Not Found",
                self.el("h1").text
            )

    def test_person_hidden_when_org_set_and_host_user_not_in_org_and_is_host_only(self):
        # Given there is an officer record named "Miesha Britton"
        # And the record is marked for_host_only
        person = Person.objects.create(
            name="Miesha Britton",
            is_law_enforcement=True,
            for_host_only=True
        )

        # Given there's an FDP Organization access control on it
        fdp_organization = FdpOrganization.objects.create(name='Test Organization')
        person.fdp_organizations.add(fdp_organization)

        # Given I'm not in the FDP Organization
        # But I am a host user
        self.log_in(
            is_administrator=False,
            is_host=True  # <- This
        )

        # When I do a search for "Miesha Britton"
        self.browser.get(self.live_server_url + '/officer/search-roundup')
        wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
            .send_keys("Miesha Britton")
        self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
            .click()

        # Then the page should say "No results found"
        self.assertIn(
            'No results found',
            self.el('.search-results').text
        )

        with self.subTest(msg="Officer links"):
            # When I go to the officer profile page
            self.browser.get(f'{self.live_server_url}/officer/{person.pk}')

            # Then I should get a 404 error
            self.assertIn(
                "Not Found",
                self.el("h1").text
            )

    # Trying to refactor the above into an easy to read truth table
    # Not working though because of some kind of flakyness related to user account creation or authentication
    # def test_matrix(self):
    #
    #     class Scenario:
    #         def __init__(
    #                 self,
    #                 rec_host_only_is_true,
    #                 rec_fdp_org_is_set,
    #                 user_is_host,
    #                 user_is_in_org,
    #                 record_should_be_hidden
    #         ):
    #             self.record_should_be_hidden = record_should_be_hidden
    #             self.rec_host_only_is_true = rec_host_only_is_true
    #             self.rec_fdp_org_is_set = rec_fdp_org_is_set
    #             self.user_is_host = user_is_host
    #             self.user_is_in_org = user_is_in_org
    #
    #         def __str__(self):
    #             return(f"{self.rec_host_only_is_true} {self.rec_fdp_org_is_set} {self.user_is_host} "
    #                    f"{self.user_is_in_org} {self.record_should_be_hidden}")
    #
    #     scenarios = [
    #         #         rec_host_only_is_true  rec_fdp_org_is_set  user_is_host  user_is_in_org, record_should_be_hidden
    #         Scenario(True, True, False, False, True),
    #         Scenario(True, True, True, False, True),
    #         Scenario(False, True, False, False, True),
    #     ]
    #
    #     for scenario in scenarios:
    #         # Given
    #         #
    #         #
    #         with self.subTest(msg=scenario):
    #             with transaction.atomic():  # Maintain test isolation
    #
    #                 # Record
    #                 person = Person.objects.create(
    #                     name="Miesha Britton",
    #                     is_law_enforcement=True,
    #                 )
    #                 if scenario.rec_host_only_is_true:
    #                     person.for_host_only = True
    #                 else:
    #                     person.for_host_only = False
    #                 person.save()
    #
    #                 fdp_organization = FdpOrganization.objects.create(name='Test Organization')
    #                 if scenario.rec_fdp_org_is_set:
    #                     person.fdp_organizations.add(fdp_organization)
    #
    #                 # User
    #                 user = self.log_in()
    #
    #                 if scenario.user_is_host:
    #                     user.is_host = True
    #                 if scenario.user_is_in_org:
    #                     user.fdp_organization.add(fdp_organization)
    #
    #                 # When
    #                 # When I do a search for "Miesha Britton"
    #                 self.browser.get(self.live_server_url + '/officer/search-roundup')
    #                 wait(self.browser.find_element, By.CSS_SELECTOR, 'input[name="q"]') \
    #                     .send_keys("Miesha Britton")
    #                 self.browser.find_element(By.CSS_SELECTOR, "input[value='Search']") \
    #                     .click()
    #
    #                 # Then
    #                 if scenario.record_should_be_hidden:
    #                     self.assertIn(
    #                         'No results found',
    #                         self.el('.search-results').text
    #                     )
    #                 else:
    #                     self.assertNotIn(
    #                         'No results found',
    #                         self.el('.search-results').text
    #                     )
    #
    #                 self.log_out()
    #
    #                 transaction.set_rollback(True)  # ... maintain test isolation
