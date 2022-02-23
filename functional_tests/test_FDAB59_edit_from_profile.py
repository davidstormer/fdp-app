from functional_tests.common import SeleniumFunctionalTestCase, wait, FunctionalTestCase

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

from lxml.html.soupparser import fromstring


class EditLinksTestCase(FunctionalTestCase):
    """Functional tests specific to the Officer profile page
    """

    @local_test_settings_required
    def test_edit_links_on_contents_linked_to_incidents(self):
        """Check that edit links are on contents when they are linked to a person with no incident
        """
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        incidents = []
        contents = []
        for i_incidents in range(3):
            new_incident = Incident.objects.create(description=f"{i_incidents}")
            incidents.append(new_incident)
            PersonIncident.objects.create(person=person_record, incident=new_incident)
            # and three content records linked under each incident record AND to the content records (for allegations)
            for i_contents in range(3):
                new_content = Content.objects.create(name=f"{i_contents}")
                new_content.incidents.add(new_incident)
                contents.append(new_content)

        # and I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the person profile page
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # and I should see content edit record links
        for content in contents:
            self.assertContains(response_admin_client, content.get_edit_url)

    @local_test_settings_required
    def test_edit_links_on_contents_without_incidents(self):
        """Check that edit links are on contents when they are linked to a person with no incident
        """
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # and there are three content records linked directly to the person
        contents = []
        for i_contents_for_person in range(3):
            new_content = Content.objects.create(name=f"{i_contents_for_person}")
            content_person = ContentPerson.objects.create(person=person_record, content=new_content)
            contents.append(new_content)

        # and I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the person profile page
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # and I should see content edit record links
        for content in contents:
            self.assertContains(response_admin_client, content.get_edit_url)

    @local_test_settings_required
    def test_edit_links_on_incidents(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # and there are three incident records linked to the person record
        incidents = []
        for i_incidents in range(3):
            new_incident = Incident.objects.create(description=f"{i_incidents}")
            incidents.append(new_incident)
            PersonIncident.objects.create(person=person_record, incident=new_incident)

        # and I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the person profile page
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # and I should see incident edit record links
        for incident in incidents:
            self.assertContains(response_admin_client, incident.get_edit_url)

    @local_test_settings_required
    def test_edit_links_on_identification_and_associates_sections(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # and I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the person profile page
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see two person edit record links (for each section: Identification, Associates)
        self.assertContains(response_admin_client, person_record.get_edit_url, count=2)

    @local_test_settings_required
    def test_edit_links_on_incident_allegations(self):
        """Check that there are edit links on allegations on contents that are linked to incidents.
        And NOT allegations on contents that aren't linked to incidents.
        """
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        #
        #
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # AND there are three incident records linked to the person record
        incidents = []
        contents = []
        allegations = []
        for i_incidents in range(3):
            new_incident = Incident.objects.create(description=f"{i_incidents}")
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
        # AND I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # WHEN I go to the person profile page
        #
        #
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # THEN I should see the allegation edit links
        #
        #
        for content in contents:
            self.assertContains(response_admin_client, content.get_allegations_penalties_edit_url)

    @local_test_settings_required
    def test_edit_links_on_allegations_without_incidents(self):
        """Check that there are edit links on allegations on contents that aren't linked to incidents.
        And NOT allegations on contents that are linked to incidents.
        """
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        #
        #
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # AND there are three content records linked to the person record
        contents = []
        allegations = []
        for i_contents in range(3):
            new_content = Content.objects.create(name=f"{i_contents}")
            contents.append(new_content)
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
        # AND I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # WHEN I go to the person profile page
        #
        #
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # THEN I should see the allegation edit links
        #
        #
        for content in contents:
            self.assertContains(response_admin_client, content.get_allegations_penalties_edit_url)

    @local_test_settings_required
    def test_edit_links_visible_to_admins_only(self):
        """Note: this is purely for usability reasons, not security.
        """
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # and there is an incident record linked to the person record
        incident_record = Incident.objects.create(description="noncanvassing")
        PersonIncident.objects.create(person=person_record, incident=incident_record)
        # and there is a content record linked to the incident
        content_record_on_incident = Content.objects.create(name="trustmonger")
        content_record_on_incident.incidents.add(incident_record)
        # and there are allegations and penalties linked to the content that is linked to the incident
        content_person = ContentPerson.objects.create(person=person_record, content=content_record_on_incident)
        allegation_type_on_incident = Allegation.objects.create(name=f'allegation-{uuid4()}')
        allegation_outcome_type_on_incident = \
            AllegationOutcome.objects.create(name=f"allegation-outcome-{uuid4()}")
        allegation_on_incident = ContentPersonAllegation.objects.create(
            content_person=content_person,
            allegation=allegation_type_on_incident,
            allegation_outcome=allegation_outcome_type_on_incident
        )
        # And a penalty is linked to the person content link
        penalty_on_incident = ContentPersonPenalty.objects.create(
            content_person=content_person,
            penalty_requested=f"hyphomycetic",
            penalty_received=f"penalty-received-{uuid4()}",
            discipline_date=datetime(1922, 1, 1)
        )
        # and there is a content record linked directly to the person
        content_record_on_person = Content.objects.create(name="baptismally")
        content_person = ContentPerson.objects.create(person=person_record, content=content_record_on_person)
        # And an allegation is linked to the content
        allegation_type_on_content = Allegation.objects.create(name=f'allegation-{uuid4()}')
        allegation_outcome_type = \
            AllegationOutcome.objects.create(name=f"allegation-outcome-{uuid4()}")
        allegation_on_content = ContentPersonAllegation.objects.create(
            content_person=content_person,
            allegation=allegation_type_on_content,
            allegation_outcome=allegation_outcome_type
        )
        # And a penalty is linked to the person content link
        penalty_on_content = ContentPersonPenalty.objects.create(
            content_person=content_person,
            penalty_requested=f"hyphomycetic",
            penalty_received=f"penalty-received-{uuid4()}",
            discipline_date=datetime(1922, 1, 1)
        )

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should NOT see Person edit links
        self.assertNotContains(response_staff_client, person_record.get_edit_url)
        # and I should NOT see Incident edit links
        self.assertNotContains(response_staff_client, incident_record.get_edit_url)
        # and I should NOT see Content edit links linked under incidents
        self.assertNotContains(response_staff_client, content_record_on_incident.get_edit_url)
        # and I should NOT see Content edit links linked directly under the person
        self.assertNotContains(response_staff_client, content_record_on_person.get_edit_url)
        # and I should NOT see Allegation edit links linked under the incident
        self.assertNotContains(response_staff_client, allegation_on_incident.get_allegations_penalties_edit_url)
        # and I should NOT see Allegation edit links linked under the content
        self.assertNotContains(response_staff_client, allegation_on_content.get_allegations_penalties_edit_url)
        # and I should NOT see Penalty edit links linked under the incident
        self.assertNotContains(response_staff_client, penalty_on_incident.get_allegations_penalties_edit_url)
        # and I should NOT see Penalty edit links linked under the content
        self.assertNotContains(response_staff_client, penalty_on_content.get_allegations_penalties_edit_url)

        # and I should NOT see edit links of any kind whatever!
        document = fromstring(response_staff_client.content)
        link_tags = document.cssselect('a')
        for link_tag in link_tags:
            tag_text = ' '.join(link_tag.itertext())
            self.assertNotIn(tag_text.upper(), 'edit'.upper())

    @local_test_settings_required
    def test_get_allegations_penalties_edit_url(self):
        # GIVEN there's an officer record
        #
        #
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # And there is a content record linked to the person
        content_record = Content.objects.create(name=f"content-name-{uuid4()}")
        content_person = ContentPerson.objects.create(person=person_record, content=content_record)
        # And an allegation is linked to the content
        allegation_type = Allegation.objects.create(name=f'allegation-{uuid4()}')
        allegation_outcome_type = \
            AllegationOutcome.objects.create(name=f"allegation-outcome-{uuid4()}")
        allegation = ContentPersonAllegation.objects.create(
            content_person=content_person,
            allegation=allegation_type,
            allegation_outcome=allegation_outcome_type
        )
        # And a penalty is linked to the person content link
        penalty = ContentPersonPenalty.objects.create(
            content_person=content_person,
            penalty_requested=f"hyphomycetic",
            penalty_received=f"penalty-received-{uuid4()}",
            discipline_date=datetime(1922, 1, 1)
        )
        # And I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # WHEN I get the get_allegations_penalties_edit_url property from the content record
        #
        #
        url = content_record.get_allegations_penalties_edit_url
        # and I go to the link
        response = admin_client.get(url)

        # THEN I should see the allegations and penalties edit page
        #
        #
        self.assertContains(
            response,
            '<h1>Link Allegations and Penalties</h1>'
        )


class EditFromProfileTests(SeleniumFunctionalTestCase):

    @local_test_settings_required
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

    @local_test_settings_required
    def test_edit_links_on_content_penalties(self):
        """Check that there are edit links on penalties on contents that are NOT linked to incidents.
        And NOT penalties on contents that are linked to incidents.
        """
        b = self.browser

        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        #
        #
        person_record = Person.objects.create(name=f"person-name-{uuid4()}", is_law_enforcement=True)
        contents = []
        allegations = []
        penalties = []
        # AND three content records are linked to the person
        for i_contents in range(3):
            new_content = Content.objects.create(name=f"{i_contents}")
            contents.append(new_content)
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

        # THEN I should see the penalty edit links under their respective contents
        #
        #

        for content in contents:
            # ... for a given content get all of the penalties associated with the person

            # Get content person links linked to person
            content_persons = ContentPerson.objects.filter(person=person_record)
            # Get penalties linked to those content_person links
            penalties = ContentPersonPenalty.objects.filter(content_person__in=content_persons)

            # Assert that edit url is on each penalty in the content section on the page
            for penalty in penalties:
                content_element = b.find_element_by_css_selector(f'div.content-{content.pk}')
                edit_link_element = \
                    content_element.find_element_by_xpath(f"//*[contains(text(), '{penalty.penalty_received}')]/a")
                self.assertEqual(
                    penalty.get_allegations_penalties_edit_url,
                    urlparse(edit_link_element.get_attribute('href')).path
                )

            # TODO: update the allegations test cause it doesn't use selectors !!! :d
            # self.assertContains(response_admin_client, content.get_allegations_penalties_edit_url)

    @local_test_settings_required
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

    @local_test_settings_required
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
