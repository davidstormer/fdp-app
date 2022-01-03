import pdb
import uuid
from random import randint
from uuid import uuid4
from django.urls import reverse
from inheritable.tests import AbstractTestCase, local_test_settings_required
from fdpuser.models import FdpOrganization, FdpUser
from core.models import (
    Person,
    PersonIncident,
    Incident,
    PersonRelationship,
    Grouping,
    PersonGrouping,
    GroupingIncident,
    PersonAlias,
    PersonTitle,
    Title,
    PersonIdentifier,
    PersonIdentifierType,
    PersonGroupingType,
)
from sourcing.models import (
    Attachment,
    Content,
    ContentPerson,
    ContentIdentifier,
    ContentCase,
    ContentPersonAllegation,
    ContentPersonPenalty
)
from supporting.models import (
    PersonRelationshipType,
    ContentIdentifierType,
    Trait,
    TraitType,
    Allegation,
    AllegationOutcome,
)
from django.test import Client
from datetime import datetime, timedelta
from lxml.html.soupparser import fromstring

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

    def associate_people(self, subject_person: object, object_person: object) -> object:
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

    @local_test_settings_required
    def test_person_associates_displayed(self):
        """Functional test
        """
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # AND there are multiple other officer records linked to it
        associate1 = Person.objects.create(name=f"associate-1-{uuid4()}", is_law_enforcement=True)
        associate2 = Person.objects.create(name=f"associate-2-{uuid4()}", is_law_enforcement=True)
        associate3 = Person.objects.create(name=f"associate-3-{uuid4()}", is_law_enforcement=True)
        relationship_type1 = self.associate_people(person_record, associate1)
        relationship_type2 = self.associate_people(person_record, associate2)
        relationship_type3 = self.associate_people(person_record, associate3)
        # AND I'm logged in as a staff user (non-admin)
        staff_client = self.log_in(is_administrator=False)

        # WHEN I got to the officer's profile page
        response_staff_client = staff_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)

        # THEN I should see the officers names linked under the Associates section
        self.assertContains(
            response_staff_client,
            associate1.name
        )
        self.assertContains(
            response_staff_client,
            associate2.name
        )
        self.assertContains(
            response_staff_client,
            associate3.name
        )
        # AND I should see their relationship types
        self.assertContains(
            response_staff_client,
            relationship_type1.name
        )
        self.assertContains(
            response_staff_client,
            relationship_type2.name
        )
        self.assertContains(
            response_staff_client,
            relationship_type3.name
        )

    @local_test_settings_required
    def test_incident_allegations_and_penalties_displayed(self):
        """Functional test
        """
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        #
        #
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # And there's an incident record linked to it
        incident_record = Incident.objects.create(description=f"incident-description-{uuid4()}")
        PersonIncident.objects.create(
            person=person_record,
            incident=incident_record
        )
        # And there's a content records linked to the incident
        content_record = Content.objects.create(name=f"content-name-{uuid4()}")
        content_record.incidents.add(incident_record)
        # And the content record is linked to person too
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
            penalty_requested=f"heliotypography",
            penalty_received=f"penalty-received-{uuid4()}",
            discipline_date=datetime(1922, 1, 1)
        )
        # And I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # WHEN I go to the person profile page
        #
        #
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)
        document = fromstring(response_admin_client.content)

        # THEN I should see the allegation type under the incident
        #
        #
        allegation_types_under_incidents = \
            document.cssselect(f"div.incident.incident-{incident_record.pk} li.allegation .allegation-type")
        if allegation_types_under_incidents:
            self.assertEqual(
                allegation_types_under_incidents[0].text,
                allegation_type.name
            )
        else:
            self.fail(f"Couldn't find any allegation types under incident {incident_record}")

        # AND the allegation outcomes
        allegation_outcomes_under_incidents = \
            document.cssselect(f"div.incident.incident-{incident_record.pk} li.allegation .allegation-outcome")
        if allegation_outcomes_under_incidents:
            self.assertEqual(
                allegation_outcomes_under_incidents[0].text,
                allegation_outcome_type.name
            )
        else:
            self.fail(f"Couldn't find any allegation outcomes under incident {incident_record}")

        # AND the penalty received AND discipline date
        penalties_under_incidents = \
            document.cssselect(f"div.incident.incident-{incident_record.pk} li.penalty")

        def normalize_whitespace(input_string: str) -> str:
            return " ".join(input_string.split())

        if penalties_under_incidents:
            self.assertEqual(
                normalize_whitespace(' '.join(penalties_under_incidents[0].itertext())),
                normalize_whitespace(f"On {penalty.discipline_date.strftime('%d/%m/%Y')}, {penalty.penalty_received} edit")
            )
        else:
            self.fail(f"Couldn't find any penalties under incident {incident_record}")

        # AND *NOT* the penalty requested
        self.assertNotContains(
            response_admin_client,
            'heliotypography'
        )

    @local_test_settings_required
    def test_content_allegations_and_penalties_displayed(self):
        """Functional test
        """
        # GIVEN there is an 'officer record' (Person record in the system set as law enforcement)
        #
        #
        person_record = Person.objects.create(name="Test person", is_law_enforcement=True)
        # And there is a content record linked to the person
        content_record = Content.objects.create(name=f"content-name-{uuid4()}")
        content_person = ContentPerson.objects.create(person=person_record, content=content_record)

        # And there is *NO* incident record linked to it
        # incident_record = Incident.objects.create(description=f"incident-description-{uuid4()}")
        # PersonIncident.objects.create(
        #     person=person_record,
        #     incident=incident_record
        # )
        # content_record.incidents.add(incident_record)

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

        # WHEN I go to the person profile page
        #
        #
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)
        document = fromstring(response_admin_client.content)

        # THEN I should see the allegation type under the incident
        #
        #
        allegation_types_under_incidents = \
            document.cssselect(f"div.content.content-{content_record.pk} li.allegation .allegation-type")
        if allegation_types_under_incidents:
            self.assertEqual(
                allegation_types_under_incidents[0].text,
                allegation_type.name
            )
        else:
            self.fail(f"Couldn't find any allegation types under content {content_record}")

        # AND I should see the allegation outcomes
        allegation_outcomes_under_incidents = \
            document.cssselect(f"div.content.content-{content_record.pk} li.allegation .allegation-outcome")
        if allegation_outcomes_under_incidents:
            self.assertEqual(
                allegation_outcomes_under_incidents[0].text,
                allegation_outcome_type.name
            )
        else:
            self.fail(f"Couldn't find any allegation outcomes under content {content_record}")

        def normalize_whitespace(input_string: str) -> str:
            return " ".join(input_string.split())

        # AND I should see the penalty received AND discipline date
        penalties_under_incidents = \
            document.cssselect(f"div.content.content-{content_record.pk} li.penalty")
        if penalties_under_incidents:
            self.assertEqual(
                normalize_whitespace(' '.join(penalties_under_incidents[0].itertext())),
                normalize_whitespace(f"On {penalty.discipline_date.strftime('%d/%m/%Y')}, {penalty.penalty_received} edit")
            )
        else:
            self.fail(f"Couldn't find any penalties under content {content_record}")

        # AND *NOT* the penalty requested
        self.assertNotContains(
            response_admin_client,
            'hyphomycetic'
        )

    def test_incident_class_contains_pk(self):
        """Rules out the possibility that the pk of another model is being used -- which yes for reals totally happened!
        """
        # Given there are a random number of incident records in the system
        for i in range(randint(0, 25)):
            Incident.objects.create(description="Existing incident")
        # And I create one more with a unique name
        incident = Incident.objects.create(description=f"incident-description-{uuid4()}")
        # And I link it to a Person record
        person_record = Person.objects.create(name="Hello World", is_law_enforcement=True)
        PersonIncident.objects.create(incident=incident, person=person_record)
        # And I'm logged into the system as an Admin
        admin_client = self.log_in(is_administrator=True)

        # WHEN I go to the person profile page
        #
        #
        response_admin_client = admin_client.get(reverse(
            'profiles:officer',
            kwargs={'pk': person_record.pk}), follow=True)
        document = fromstring(response_admin_client.content)
        # Then the record located by the id should have the correct name
        incident_element = document.cssselect(f'section.misconduct div.incident.incident-{incident.pk}')
        self.assertIn(
            incident.description,
            incident_element[0].text_content()
        )
        # self.assertContains(response_admin_client, f"incident-{incident.pk}")
