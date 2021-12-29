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
from urllib.parse import urlparse


class EditFromProfileTests(SeleniumFunctionalTestCase):

    def test_edit_links_on_incident_penalties(self):
        """Check that there are edit links on penalties on contents that are linked to incidents.
        And NOT penalties on contents that aren't linked to incidents.
        """
        b = self.browser

        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        #
        #
        person_record = Person.objects.create(name=f"person-name-{uuid4()}", is_law_enforcement=True)
        # AND there are three incident records linked to the person record
        incidents = []
        contents = []
        allegations = []
        penalties = []
        for i_incidents in range(3):
            new_incident = Incident.objects.create(description=f"incident-description-{uuid4()}")
            incidents.append(new_incident)
            PersonIncident.objects.create(person=person_record, incident=new_incident)
            # AND three content records linked under each incident record AND to the content records (for allegations)
            for i_contents in range(3):
                new_content = Content.objects.create(name=f"{i_contents}")
                contents.append(new_content)
                new_content.incidents.add(new_incident)
                content_person = ContentPerson.objects.create(person=person_record, content=new_content)
                # AND three allegations linked under each content record
                for i_allegation in range(3):
                    allegation_type = Allegation.objects.create(name=f'allegation-{uuid4()}')
                    allegation_outcome_type = \
                        AllegationOutcome.objects.create(name=f"allegation-outcome-{uuid4()}")
                    new_allegation = ContentPersonAllegation.objects.create(
                        content_person=content_person,
                        allegation=allegation_type,
                        allegation_outcome=allegation_outcome_type
                    )
                    allegations.append(new_allegation)
                # And three penalties linked to the person content link
                for i_penalty in range(3):
                    new_penalty = ContentPersonPenalty.objects.create(
                        content_person=content_person,
                        penalty_requested=f"hyphomycetic",
                        penalty_received=f"penalty-received-{uuid4()}",
                        discipline_date=datetime(1922, 1, 1)
                    )
                    penalties.append(new_penalty)

        # AND I'm logged into the system as an Admin
        self.log_in(is_administrator=True)

        # WHEN I go to the person profile page
        #
        #
        self.browser.get(self.live_server_url + reverse('profiles:officer', kwargs={'pk': person_record.pk}))

        # THEN I should see the penalty edit links under their respective incidents
        #
        #

        for incident in incidents:
            # ... for a given incident get all of the penalties associated with the person

            # Get content person links linked to both person and the given incident
            content_persons = ContentPerson.objects.filter(person=person_record) \
                .filter(content__in=Content.objects.filter(incidents=incident))
            # Get penalties linked to those content_person links
            penalties = ContentPersonPenalty.objects.filter(content_person__in=content_persons)

            # Assert that edit url of each penalty is the incident section on the page

            edit_link_urls = {
                urlparse(link_element.get_attribute('href')).path for link_element in
                b.find_elements_by_css_selector(f'div.incident-{incident.pk} li.penalty a')}
            for penalty in penalties:
                self.assertIn(
                    penalty.get_allegations_penalties_edit_url,
                    edit_link_urls
                )
            # TODO: update the allegations test cause it doesn't use selectors !!! :d
            # self.assertContains(response_admin_client, content.get_allegations_penalties_edit_url)

    def test_AllegationPenaltyLinkUpdateView_next_redirect_no_incident(self):
        # GIVEN there's an allegation record *with no linked incident*
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
        officer_profile_url = reverse('profiles:officer', kwargs={'pk': person_record.pk})
        self.browser.get(
            self.live_server_url +
            content_record.get_allegations_penalties_edit_url +
            f"?next={officer_profile_url}")
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

    def test_AllegationPenaltyLinkUpdateView_next_redirect_with_incident(self):
        # GIVEN there's an allegation record *on content linked to an incident*
        #
        #
        # ... first need a Person record
        person_record = Person.objects.create(name=f"person-name-{uuid4()}", is_law_enforcement=True)
        # ... *and an incident record*
        new_incident = Incident.objects.create(description=f"incident-description-{uuid4()}")
        PersonIncident.objects.create(person=person_record, incident=new_incident)
        # ... and a content record linked to the person *and the incident*
        content_record = Content.objects.create(name=f"content-name-{uuid4()}")
        content_person = ContentPerson.objects.create(person=person_record, content=content_record)
        content_record.incidents.add(new_incident)
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
        officer_profile_url = reverse('profiles:officer', kwargs={'pk': person_record.pk})
        self.browser.get(
            self.live_server_url +
            content_record.get_allegations_penalties_edit_url +
            f"?next={officer_profile_url}")
        # and I save the form
        self.browser.find_element_by_css_selector("input[type='submit'][value='Save']") \
            .click()

        # THEN I should be taken to the officer profile page (and not the incident edit page)
        #
        #
        heading = wait(self.browser.find_element_by_css_selector, 'div#content h1')
        self.assertEqual(
            person_record.name,
            heading.text
        )
