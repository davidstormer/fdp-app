from django.test import TestCase
from core.models import Person, PersonIncident
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait
from inheritable.tests import local_test_settings_required
from unittest import expectedFailure, skip
import pdb
from sourcing.models import Incident
from selenium.webdriver.common.by import By


class SeleniumTestCase(SeleniumFunctionalTestCase):

    def test_incident_sort_order(self):
        b = self.browser
        # Given there is an incident A (collagen) that started in 2019
        incident_a = Incident.objects.create(description="incident-a-collagen",
                                             start_year=1999)
        # and an incident C (breeder) that started in 2001
        incident_c = Incident.objects.create(description="incident-c-breeder",
                                             start_year=2001)
        # and an incident B (possum) that started in 2000
        incident_b = Incident.objects.create(description="incident-b-possum",
                                             start_year=2000)
        # and an incident D (handful) that has no start date (0-0-0)
        incident_d = Incident.objects.create(description="incident-d-handful",
                                             start_year=0,
                                             start_month=0,
                                             start_day=0)
        # and an incident E (cremated) that that has no start year (0),
        #   but a start month of january and a start day of the 1st
        incident_e = Incident.objects.create(description="incident-e-cremated",
                                             start_year=0,
                                             start_month=1,
                                             start_day=1)
        # and the above incidents are associated with an officer record
        officer = Person.objects.create(name='Test Officer Towboat', is_law_enforcement=True)
        PersonIncident.objects.create(person=officer, incident=incident_a)
        PersonIncident.objects.create(person=officer, incident=incident_b)
        PersonIncident.objects.create(person=officer, incident=incident_c)
        PersonIncident.objects.create(person=officer, incident=incident_d)
        PersonIncident.objects.create(person=officer, incident=incident_e)

        # and I'm logged into the system as an Admin
        self.log_in(is_administrator=True)
        heading = wait(self.browser.find_element_by_css_selector, 'div#content h1')
        self.assertEqual(
            "What are you searching for?",
            heading.text
        )

        # WHEN I go to the officer profile page
        b.get(self.live_server_url + f'/officer/{officer.pk}')

        incident_elements = wait(b.find_elements, By.CSS_SELECTOR, 'section.misconduct div.incident')

        # THEN I should see
        #   Incident C placed at the top of the list
        self.assertIn(
            'incident-c-breeder',
            incident_elements[0].text
        )
        #   Incident B placed second to the top of the list
        self.assertIn(
            'incident-b-possum',
            incident_elements[1].text
        )
        #   Incident A placed third to the top of the list
        self.assertIn(
            'incident-a-collagen',
            incident_elements[2].text
        )
        #   Incident E placed fourth to the top of the list
        self.assertIn(
            'incident-e-cremated',
            incident_elements[3].text
        )
        #   Incident D placed fifth to the top of the list
        self.assertIn(
            'incident-d-handful',
            incident_elements[4].text
        )
