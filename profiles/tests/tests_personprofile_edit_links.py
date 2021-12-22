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

import logging

logger = logging.getLogger(__name__)


class EditLinksTestCase(AbstractTestCase):
    """Functional tests specific to the Officer profile page
    """

    def log_in(self, is_host=True, is_administrator=False, is_superuser=False) -> object:
        client = Client()
        fdp_user = self._create_fdp_user(
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

    @local_test_settings_required
    def test_edit_links(self):
        """Edit links show up on the officer profile page for admins
        """
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # and there are three incident records linked to the person record
        incidents = []
        contents = []
        allegations = []
        for i_incidents in range(3):
            new_incident = Incident.objects.create(description=f"{i_incidents}")
            incidents.append(new_incident)
            PersonIncident.objects.create(person=person_record, incident=new_incident)
            # and three content records linked under each incident record AND to the content records (for allegations)
            for i_contents in range(3):
                new_content = Content.objects.create(name=f"{i_contents}")
                contents.append(new_content)
                new_content.incidents.add(new_incident)
                content_person = ContentPerson.objects.create(person=person_record, content=new_content)
                # and three allegations linked under each content record
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

        # and there are three content records linked directly to the person
        for i_contents_for_person in range(3):
            new_content = Content.objects.create(name=f"{i_contents_for_person}")
            content_person = ContentPerson.objects.create(person=person_record, content=new_content)
            contents.append(new_content)
            # and three allegations linked under each content record
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

        # and I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the person profile page
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see two person edit record links (for each section: Identification, Associates)
        self.assertContains(response_admin_client, person_record.get_edit_url, count=2)
        # and I should see incident edit record links
        for incident in incidents:
            self.assertContains(response_admin_client, incident.get_edit_url)
        # and I should see content edit record links
        for content in contents:
            self.assertContains(response_admin_client, content.get_edit_url)
        # and I should see allegation edit links
        # See below -\/
        # and I should see penalties edit links
        # TODO: test that the penalties linked both to the person and the incidents have links

    @local_test_settings_required
    def test_edit_links_incident_allegations(self):
        """Edit links show up on the allegations listed under incidents
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
        # and there is a content record linked directly to the person
        content_record_on_person = Content.objects.create(name="baptismally")
        ContentPerson.objects.create(person=person_record, content=content_record_on_person)
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
