from core.models import Person, PersonContact
from supporting.models import State
from functional_tests.common import FunctionalTestCase
from uuid import uuid4
from profiles.templatetags.profiles_extras import contact_address_in_one_line
from django.db import transaction


class ContactInfoTestCase(FunctionalTestCase):
    def test_profile_contact_info(self):
        # Given there's an officer record with a PersonContact record containing:
        #  phone_number, email, address, city, state, and zip_code
        phone_number = f"phone-number-{uuid4()}"
        email = f"email-{uuid4()}@example.com"
        address = f"address-{uuid4()}"
        city = f"city-{uuid4()}"
        state = State.objects.create(name=f"state-{uuid4()}")
        zip_code = f"zip-{uuid4()}"
        officer = Person.objects.create(
            name='Test Officer Towboat',
            is_law_enforcement=True,
        )
        PersonContact.objects.create(
                person=officer,
                phone_number=phone_number,
                email=email,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code
        )

        # and I'm logged into the system
        client = self.log_in()

        # WHEN I go to the officer profile page
        response = client.get(f'/officer/{officer.pk}')

        # Then I should see the phone_number, email, address, city, state, and zip_code printed on the page
        self.assertContains(
            response,
            phone_number
        )
        self.assertContains(
            response,
            email
        )
        self.assertContains(
            response,
            address
        )
        self.assertContains(
            response,
            city
        )
        self.assertContains(
            response,
            state
        )
        self.assertContains(
            response,
            zip_code
        )

    def test_contact_address_in_one_line(self):
        # Given there's a PersonContact
        person = Person.objects.create(
            name='Test Person',
        )
        state = State.objects.create(name="District of Columbia")
        contact = PersonContact.objects.create(
                person=person,
                phone_number='phone_number',
                email='email@example.com',
                address='919 Cummings Locks Suite 216',
                city='North Ryanfort',
                state=state,
                zip_code='49355'
        )

        # When I format it through the contact_address_in_one_line() filter
        result = contact_address_in_one_line(contact)
        # THEN I should get a one line address that reads:
        # "919 Cummings Locks Suite 216, North Ryanfort, District of Columbia 49355"
        self.assertEqual(
            "919 Cummings Locks Suite 216, North Ryanfort, District of Columbia 49355",
            result
        )

    def test_contact_address_in_one_line_combinations(self):

        # Given the following truth table...
        truth_table = [
            # 0 0000
            {
                'output': "",
                'input': {
                    'address': '',
                    'city': '',
                    'state': None,
                    'zip_code': ''
                }
            },
            # 1 0001
            {
                'output': "49355",
                'input': {
                    'address': '',
                    'city': '',
                    'state': None,
                    'zip_code': '49355'
                }
            },
            # 2 0010
            {
                'output': "District of Columbia",
                'input': {
                    'address': '',
                    'city': '',
                    'state': "District of Columbia",
                    'zip_code': ''
                }
            },
            # 3 0011
            {
                'output': "District of Columbia 49355",
                'input': {
                    'address': '',
                    'city': '',
                    'state': "District of Columbia",
                    'zip_code': '49355'
                }
            },
            # 4 0100
            {
                'output': "North Ryanfort",
                'input': {
                    'address': '',
                    'city': 'North Ryanfort',
                    'state': None,
                    'zip_code': ''
                }
            },
            # 5 0101
            {
                'output': "North Ryanfort, 49355",
                'input': {
                    'address': '',
                    'city': 'North Ryanfort',
                    'state': None,
                    'zip_code': '49355'
                }
            },
            # 6 0110
            {
                'output': "North Ryanfort, District of Columbia",
                'input': {
                    'address': '',
                    'city': 'North Ryanfort',
                    'state': "District of Columbia",
                    'zip_code': ''
                }
            },
            # 7 0111
            {
                'output': "North Ryanfort, District of Columbia 49355",
                'input': {
                    'address': '',
                    'city': 'North Ryanfort',
                    'state': "District of Columbia",
                    'zip_code': '49355'
                }
            },
            # 8 1000
            {
                'output': "919 Cummings Locks Suite 216",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': '',
                    'state': None,
                    'zip_code': ''
                }
            },
            # 9 1001
            {
                'output': "919 Cummings Locks Suite 216, 49355",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': '',
                    'state': None,
                    'zip_code': '49355'
                }
            },
            # 10 1010
            {
                'output': "919 Cummings Locks Suite 216, District of Columbia",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': '',
                    'state': "District of Columbia",
                    'zip_code': ''
                }
            },
            # 11 1011
            {
                'output': "919 Cummings Locks Suite 216, District of Columbia 49355",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': '',
                    'state': "District of Columbia",
                    'zip_code': '49355'
                }
            },
            # 12 1100
            {
                'output': "919 Cummings Locks Suite 216, North Ryanfort",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': 'North Ryanfort',
                    'state': None,
                    'zip_code': ''
                }
            },
            # 13 1101
            {
                'output': "919 Cummings Locks Suite 216, North Ryanfort, 49355",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': 'North Ryanfort',
                    'state': None,
                    'zip_code': '49355'
                }
            },
            # 14 1110
            {
                'output': "919 Cummings Locks Suite 216, North Ryanfort, District of Columbia",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': 'North Ryanfort',
                    'state': "District of Columbia",
                    'zip_code': ''
                }
            },
            # 15 1111
            {
                'output': "919 Cummings Locks Suite 216, North Ryanfort, District of Columbia 49355",
                'input': {
                    'address': '919 Cummings Locks Suite 216',
                    'city': 'North Ryanfort',
                    'state': "District of Columbia",
                    'zip_code': '49355'
                }
            },
        ]
        # GIVEN the above inputs
        #
        #
        for i, scenario in enumerate(truth_table):
            with self.subTest(scenario=(i, scenario)):
                with transaction.atomic():  # Maintain test isolation
                    person = Person.objects.create(name='Test Person')
                    self.assertEqual(1, len(Person.objects.all()))
                    if scenario['input']['state']:
                        contact = PersonContact.objects.create(
                            person=person,
                            phone_number='phone_number',
                            email='email@example.com',
                            address=scenario['input']['address'],
                            city=scenario['input']['city'],
                            state=State.objects.create(name=scenario['input']['state']),
                            zip_code=scenario['input']['zip_code']
                        )
                    else:
                        contact = PersonContact.objects.create(
                            person=person,
                            phone_number='phone_number',
                            email='email@example.com',
                            address=scenario['input']['address'],
                            city=scenario['input']['city'],
                            # state=State.objects.create(name=scenario['input']['state']),
                            zip_code=scenario['input']['zip_code']
                        )

                    # WHEN I format them through the contact_address_in_one_line() filter
                    #
                    #
                    result = contact_address_in_one_line(contact)

                    # THEN I should get outputs that read as the above outputs, respectively
                    #
                    #
                    self.assertEqual(
                        scenario['output'],
                        result.strip()
                    )
                    transaction.set_rollback(True)  # Maintain test isolation
