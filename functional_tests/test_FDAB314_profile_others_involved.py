from core.models import Person, PersonIncident
from functional_tests.common import FunctionalTestCase, wait
from inheritable.tests import local_test_settings_required
from sourcing.models import Incident
from lxml.html.soupparser import fromstring
from uuid import uuid4
from supporting.models import SituationRole


class OthersInvolvedTestCase(FunctionalTestCase):

    @local_test_settings_required
    def test_incident_non_officers_involved(self):

        # Given there is an incident with non-officers linked to it
        incident_a = Incident.objects.create(description="incident-a")
        non_officer = Person.objects.create(name=f'non-officer-{uuid4()}',
                                            is_law_enforcement=False)  # <- non-officer
        PersonIncident.objects.create(person=non_officer, incident=incident_a)

        # and I associate the incident with an officer record
        officer = Person.objects.create(name='Test Officer Towboat', is_law_enforcement=True)
        PersonIncident.objects.create(person=officer, incident=incident_a)

        # and I'm logged into the system
        client = self.log_in()

        # WHEN I go to the officer profile page
        response = client.get(f'/officer/{officer.pk}')

        document = fromstring(response.content)
        incident_element = document.cssselect('section.misconduct div.incident')[0]

        # THEN I should see the non officers listed under "Others involved"
        self.assertIn(
            non_officer.name,
            incident_element.text_content()
        )

    def test_incident_others_involved_print_situational_role(self):
        # Given there is an incident with people involved and their situation roles are set
        situation_role_a = SituationRole.objects.create(name=f"situation-role-{uuid4()}")
        situation_role_b = SituationRole.objects.create(name=f"situation-role-{uuid4()}")
        situation_role_c = SituationRole.objects.create(name=f"situation-role-{uuid4()}")

        incident_a = Incident.objects.create(description="incident-a")

        person_a = Person.objects.create(name=f'person-{uuid4()}', is_law_enforcement=True)

        PersonIncident.objects.create(
            situation_role=situation_role_a,
            person=person_a,
            incident=incident_a)
        PersonIncident.objects.create(
            situation_role=situation_role_b,
            person=Person.objects.create(name=f'person-{uuid4()}', is_law_enforcement=True),
            incident=incident_a)
        PersonIncident.objects.create(
            situation_role=situation_role_c,
            person=Person.objects.create(name=f'person-{uuid4()}', is_law_enforcement=True),
            incident=incident_a)

        # and I'm logged into the system
        client = self.log_in()

        # When I go to one of their profile pages
        response = client.get(f'/officer/{person_a.pk}')

        document = fromstring(response.content)
        incident_element = document.cssselect('section.misconduct div.incident')[0]

        # Then I should see their situation roles printed under the incident
        self.assertIn(
            situation_role_a.name,
            incident_element.text_content()
        )
        self.assertIn(
            situation_role_b.name,
            incident_element.text_content()
        )
        self.assertIn(
            situation_role_c.name,
            incident_element.text_content()
        )
