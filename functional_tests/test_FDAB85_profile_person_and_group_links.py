from functional_tests.common import SeleniumFunctionalTestCase
from selenium.webdriver.common.by import By

from uuid import uuid4
from django.urls import reverse
from inheritable.tests import local_test_settings_required
from core.models import (
    Person,
    PersonRelationship,
)
from supporting.models import (
    PersonRelationshipType
)
from lxml.html.soupparser import fromstring

import logging

logger = logging.getLogger(__name__)


class ProfilePersonGroupLinksTestCase(SeleniumFunctionalTestCase):
    """Functional tests for links from officer profile page to people and groups
    """
    def test_person_associates_displayed(self):
        """Functional test
        """
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # AND there are multiple other officer records linked to it
        associate1 = Person.objects.create(name=f"associate-1-{uuid4()}", is_law_enforcement=True)
        associate2 = Person.objects.create(name=f"associate-2-{uuid4()}", is_law_enforcement=True)
        associate3 = Person.objects.create(name=f"associate-3-{uuid4()}", is_law_enforcement=True)

        def associate_people(subject_person: object, object_person: object) -> object:
            """Associate two given people. Creates a new arbitrary PersonRelationshipType name on each call.
            Returns the resulting PersonRelationshipType.
            """
            relationship_type = PersonRelationshipType.objects.create(name=f"relationship-type-{uuid4()}")
            relationship = PersonRelationship()
            relationship.subject_person = subject_person
            relationship.object_person = object_person
            relationship.type = relationship_type
            relationship.save()
            return relationship_type

        relationship_type1 = associate_people(person_record, associate1)
        relationship_type2 = associate_people(person_record, associate2)
        relationship_type3 = associate_people(person_record, associate3)
        # AND I'm logged in as a staff user (non-admin)
        self.log_in(is_administrator=False)

        # WHEN I got to the officer's profile page and click one of the associate's names
        self.browser.get(self.live_server_url + reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}))
        self.browser.find_element(By.LINK_TEXT, associate1.name) \
            .click()

        # THEN I should see the associates profile page
        self.assertEqual(
            self.browser.find_elements(By.CSS_SELECTOR, 'h1')[1].text,  # [1] because there are two H1s!
            associate1.name
        )
