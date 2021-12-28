from functional_tests.common import SeleniumFunctionalTestCase, wait

import pdb
from uuid import uuid4
from django.urls import reverse
from inheritable.tests import AbstractTestCase, local_test_settings_required
from fdpuser.models import FdpUser
from core.models import (
    Person,
    PersonIncident,
    Incident,

)
from sourcing.models import (
    Content,
    ContentPerson,
    ContentPersonAllegation,
    ContentPersonPenalty
)
from supporting.models import (
    Allegation,
    AllegationOutcome,
)
from django.test import Client
from datetime import datetime


class EditFromProfileTests(SeleniumFunctionalTestCase):

    def test_AllegationPenaltyLinkUpdateView_next_redirect(self):
        # GIVEN there's an allegation record
        #
        #
        # ... first need a Person record
        person_record = Person.objects.create(name=f"person-name-{uuid4()}", is_law_enforcement=True)
        # ... and a content record linked to the person
        content_record = Content.objects.create(name=f"content-name-{uuid4()}")
        content_person = ContentPerson.objects.create(person=person_record, content=content_record)
        # ... and then an allegation linked to the content
        allegation_type = Allegation.objects.create(name=f'allegation-{uuid4()}')
        allegation_outcome_type = \
            AllegationOutcome.objects.create(name=f"allegation-outcome-{uuid4()}")
        allegation = ContentPersonAllegation.objects.create(
            content_person=content_person,
            allegation=allegation_type,
            allegation_outcome=allegation_outcome_type
        )
        # ... and a penalty linked to the person content link
        penalty = ContentPersonPenalty.objects.create(
            content_person=content_person,
            penalty_requested=f"hyphomycetic",
            penalty_received=f"penalty-received-{uuid4()}",
            discipline_date=datetime(1922, 1, 1)
        )
        # AND I'm logged into the system as an Admin
        self.log_in(is_administrator=True)

        # WHEN I go to the allegations and penalties edit page,
        # with the 'next' parameter set to the officer profile page
        #
        #
        officer_profile_url = {reverse('profiles:officer', kwargs={'pk': person_record.pk})}
        self.browser.get(
            self.live_server_url +
            content_record.get_allegations_penalties_edit_url +
            f"?next=/{officer_profile_url}")
        # and I save the form
        self.browser.find_element_by_css_selector("input[type='submit'][value='Save']") \
            .click()

        # THEN I should be taken to the officer profile page
        #
        #
        heading = wait(self.browser.find_element_by_css_selector, 'div#content h1')
        self.assertEqual(
            person_record.name,
            heading.text
        )
        self.take_screenshot_and_dump_html()
        pdb.set_trace()
