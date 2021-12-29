from django.test import TestCase

from core.models import Person
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from unittest import expectedFailure, skip
import pdb


class SocialMediaProfiles(SeleniumFunctionalTestCase):

    def test_social_media_profile_links(self):
        # GIVEN there is a Person record marked as law enforcement
        person_record = Person.objects.create(name="Cocanucos", is_law_enforcement=True)
        # and I'm logged in as an admin
        # call log in in common.py
        self.log_in(is_administrator=True)
        # and I go to the officer edit page
        self.browser.get(f"{self.live_server_url}/changing/persons/update/person/{person_record.pk}")
        wait(self.browser.find_element_by_id, "new-person-social-media-profile")\
            .click()

        # and I add a social media profile link to the Person record

        wait(self.browser.find_element_by_id, "id_social-media-profile-0-link_name")\
            .send_keys("bob")
        self.browser.find_element_by_id("id_social-media-profile-0-link")\
            .send_keys("https://twitter.com")
        wait(self.browser.find_element_by_css_selector, "input[type='submit'][value='Save']")\
            .click()
        wait(self.browser.find_element_by_link_text, "Personnel")

        # WHEN I go to the officer profile page
        self.browser.get(f"{self.live_server_url}/officer/{person_record.pk}")
        social_link = wait(self.browser.find_element_by_link_text, "https://twitter.com")

        # THEN I should see the social media profile link
        self.assertIn(
            "https://twitter.com",
            social_link.text
        )