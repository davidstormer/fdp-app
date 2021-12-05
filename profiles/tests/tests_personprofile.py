import pdb
import uuid
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from inheritable.tests import AbstractTestCase, local_test_settings_required
from fdpuser.models import FdpOrganization, FdpUser
from core.models import Person, PersonIncident, Incident, PersonRelationship, Grouping, PersonGrouping, \
    GroupingIncident, PersonAlias, PersonTitle, Title, PersonIdentifier, PersonIdentifierType, PersonGroupingType
from sourcing.models import Attachment, Content, ContentPerson, ContentIdentifier, ContentCase
from supporting.models import PersonRelationshipType, ContentIdentifierType, Trait, TraitType
from os.path import splitext
from django.test import Client
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PersonProfileTestCase(AbstractTestCase):
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
        # and three content records linked under each incident record
        incidents = []
        contents = []
        for i_incidents in range(3):
            new_incident = Incident.objects.create(description=f"{i_incidents}")
            incidents.append(new_incident)
            PersonIncident.objects.create(person=person_record, incident=new_incident)
            for i_contents in range(3):
                new_content = Content.objects.create(name=f"{i_contents}")
                contents.append(new_content)
                new_content.incidents.add(new_incident)
        # and there are three content records linked directly to the person
        for i_contents_for_person in range(3):
            new_content = Content.objects.create(name=f"{i_contents_for_person}")
            ContentPerson.objects.create(person=person_record, content=new_content)
            contents.append(new_content)
        # and I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # When I go to the person profile page
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see three person edit record links (for each section: Identification, Associates)
        self.assertContains(response_admin_client, person_record.get_edit_url, count=2)
        # and I should see incident edit record links
        for incident in incidents:
            self.assertContains(response_admin_client, incident.get_edit_url)
        # and I should see content edit record links
        for content in contents:
            self.assertContains(response_admin_client, content.get_edit_url)

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
    def test_incidents_displayed(self):
        """Test that the profile page displays the incidents linked to the person
        """
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # and there are three incident records linked to the person record
        descriptions = []
        for i in range(3):
            description = f"Incident description... {uuid.uuid4()}"
            incident_record = Incident.objects.create(description=description)
            descriptions.append(description)
            PersonIncident.objects.create(person=person_record, incident=incident_record)
        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the incident records listed
        for description in descriptions:
            self.assertContains(response_staff_client, description)

    @local_test_settings_required
    def test_content_displayed_under_incident(self):
        """Test that the profile page displays the incidents linked to the person
        """
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # and there are three incident records linked to the person record
        # and under each incident are linked three content records
        identifier_type = ContentIdentifierType.objects.create(name='fakeidtype')
        incident_descriptions = []
        content_identifiers = []
        for i in range(3):
            description = f"Incident description... {uuid.uuid4()}"
            new_incident_record = Incident.objects.create(description=description)
            incident_descriptions.append(description)
            PersonIncident.objects.create(person=person_record, incident=new_incident_record)
            for j in range(3):
                identifier_value = f"content-identifier-{uuid.uuid4()}"
                new_content_record = Content.objects.create()
                new_content_record.incidents.add(new_incident_record)
                identifier = ContentIdentifier.objects.create(
                    identifier=identifier_value,
                    content_identifier_type=identifier_type,
                    content=new_content_record
                )
                content_identifiers.append(identifier_value)
        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the content records listed
        for content_name in content_identifiers:
            self.assertContains(
                response_staff_client,
                content_name,
                msg_prefix="Couldn't find content under incident by id")

    @local_test_settings_required
    def test_person_content_displayed(self):
        """Test that the profile page displays the contents linked to the person (rather than the ones that are
        linked to incidents.
        """
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # and there are three content records linked directly to the person record
        descriptions = []
        for i in range(3):
            name = f"Content name... {uuid.uuid4()}"
            content_record_on_person = Content.objects.create(name=name)
            ContentPerson.objects.create(person=person_record, content=content_record_on_person)
            descriptions.append(name)

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the content records listed
        for description in descriptions:
            self.assertContains(response_staff_client, description)

    @local_test_settings_required
    def test_person_aliases_displayed(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # And they have aliases
        alias_values = []
        for i in range(3):
            name = uuid.uuid4()
            PersonAlias.objects.create(name=name, person=person_record)
            alias_values.append(name)

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the aliases listed
        for alias_value in alias_values:
            self.assertContains(response_staff_client, alias_value)

    @local_test_settings_required
    def test_person_age_displayed(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        # And the officer has a birthday set
        age_to_find = 123
        birthdate = datetime.now() - timedelta(days=365 * (age_to_find + 1))
        person_record = Person.objects.create(
            name="Test person",
            is_law_enforcement=True,
            birth_date_range_start=birthdate,
            birth_date_range_end=birthdate
        )

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see their age
        self.assertContains(
            response_staff_client,
            f"<span class='label'>Age:</span> <span>{age_to_find}</span>",
            html=True)

    @local_test_settings_required
    def test_person_titles_displayed(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # And the officer has titles
        values_to_find = []
        for i in range(3):
            value = uuid.uuid4()
            PersonTitle.objects.create(
                title=Title.objects.create(name=value),
                person=person_record)
            values_to_find.append(value)

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the aliases listed
        for value in values_to_find:
            self.assertContains(response_staff_client, value)

    @local_test_settings_required
    def test_person_traits_displayed(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # And the officer has traits
        trait_type = TraitType.objects.create(name="test trait type")
        values_to_find = []
        for i in range(3):
            value = uuid.uuid4()
            person_record.traits.add(
                Trait.objects.create(name=value, type=trait_type)
            )
            values_to_find.append(value)

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the traits listed
        for value in values_to_find:
            self.assertContains(response_staff_client, value)

    @local_test_settings_required
    def test_person_identifiers_displayed(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # And the officer has identifiers
        id_type_value = str(uuid.uuid4())
        id_type = PersonIdentifierType.objects.create(name=id_type_value)
        values_to_find = []
        for i in range(3):
            value = str(uuid.uuid4())
            PersonIdentifier.objects.create(
                person=person_record,
                identifier=value,
                person_identifier_type=id_type
            )
            values_to_find.append(value)

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the identifiers listed
        for value in values_to_find:
            self.assertContains(response_staff_client, value)
        # and their identifier types
        self.assertContains(response_staff_client, id_type_value, count=3)

    @local_test_settings_required
    def test_person_groups_displayed(self):
        # Given there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # And the officer is associated with groups
        values_to_find = []
        for i in range(3):
            value = uuid.uuid4()
            PersonGrouping.objects.create(
                person=person_record,
                grouping=Grouping.objects.create(name=value))
            values_to_find.append(value)

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the groups listed
        for value in values_to_find:
            self.assertContains(response_staff_client, value)

        # and there should be hyperlinks to the respective group profile pages
        for value in values_to_find:
            group = Grouping.objects.get(name=value)
            self.assertContains(
                response_staff_client,
                f"<a href='{group.get_profile_url}'>{value}</a>",
                html=True)

    @local_test_settings_required
    def test_no_basic_info(self):
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # AND there is no basic info
        pass
        # AND I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # WHEN I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # THEN I should NOT see the "Basic info" heading
        self.assertNotContains(response_staff_client, "Basic information")

    @local_test_settings_required
    def test_person_group_types_displayed(self):
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)

        # AND the officer is associated with groups
        # AND the associations have given types
        values_to_find = []
        for i in range(3):
            value = f"persongrouping-type-{uuid.uuid4()}"
            person_grouping_type = PersonGroupingType.objects.create(name=value)
            PersonGrouping.objects.create(
                type=person_grouping_type,
                person=person_record,
                grouping=Grouping.objects.create(name=f"grouping-name-{uuid.uuid4()}"))
            values_to_find.append(value)

        # and I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # When I go to the person profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # Then I should see the groups listed
        for value in values_to_find:
            self.assertContains(response_staff_client, value)
