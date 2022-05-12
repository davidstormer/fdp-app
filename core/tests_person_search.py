from unittest import skip
from uuid import uuid4
from django.db import transaction
from django.test import TestCase
from faker import Faker
from core.models import Person, PersonAlias, PersonIdentifier
from fdpuser.models import FdpUser, FdpOrganization
from profiles.models import OfficerSearch
from supporting.models import PersonIdentifierType

faker = Faker()


def make_fake_person_records(number):
    PersonIdentifierType.objects.create(name=uuid4())

    with transaction.atomic():
        for i in range(number):
            person_record = Person.objects.create(name=faker.name(), is_law_enforcement=True)
            PersonIdentifier.objects.create(
                identifier=f'{faker.ssn()} 1-{i}', person=person_record,
                person_identifier_type=PersonIdentifierType.objects.last())
            PersonIdentifier.objects.create(
                identifier=f'{faker.ssn()} 2-{i}', person=person_record,
                person_identifier_type=PersonIdentifierType.objects.last())
            PersonAlias.objects.create(name=faker.name(), person=person_record)
            # PersonAlias.objects.create(name=faker.name(), person=person_record)
            # PersonAlias.objects.create(name=faker.name(), person=person_record)


class FullTextIndexing(TestCase):
    def test_repopulate_search_full_text_name(self):
        # When there's a Person record
        person_record = Person.objects.create(name="echinodermal")
        # Then the full text field should reflect the changes
        self.assertIn(
            'echinodermal',
            Person.objects.last().search_full_text
        )

    def test_repopulate_search_full_text_name_diacritic_folding(self):
        # When there's a Person record with a diacritic mark in the name
        person_record = Person.objects.create(name="café")
        # Then the full text field should have a normalized form with no diacritic mark
        self.assertIn(
            'cafe',
            Person.objects.last().search_full_text
        )

    def test_repopulate_search_full_text_aliases(self):
        # Given there's a Person record
        person_record = Person.objects.create(name="Test Person")
        # When I update their aliases
        PersonAlias.objects.create(name='mastiff', person=person_record)
        PersonAlias.objects.create(name='yielding', person=person_record)
        PersonAlias.objects.create(name='henchmen', person=person_record)
        # Then the full text field should reflect the changes
        self.assertIn(
            'mastiff',
            Person.objects.last().search_full_text
        )
        self.assertIn(
            'yielding',
            Person.objects.last().search_full_text
        )
        self.assertIn(
            'henchmen',
            Person.objects.last().search_full_text
        )

    def test_repopulate_search_full_text_aliases_duplicate_names(self):
        """To prevent skewing search results"""
        # Given there's a Person record
        person_record = Person.objects.create(name="Test Person")
        # When I update their aliases with duplicate names (e.g. first name)
        PersonAlias.objects.create(name='errant mastiff', person=person_record)
        PersonAlias.objects.create(name='errant yielding', person=person_record)
        PersonAlias.objects.create(name='errant henchmen', person=person_record)
        # Then the full text field should only have ONE instance of "errant" in it
        self.assertEqual(
            1,
            Person.objects.last().search_full_text.count('errant')
        )

    def test_repopulate_search_full_text_identifiers(self):
        # Given there's a Person record
        person_record = Person.objects.create(name="Test Person")
        # When I update the identifiers for the person
        id_type = PersonIdentifierType.objects.create(name='Test Type')
        PersonIdentifier.objects.create(
            identifier='emphatic', person=person_record,
            person_identifier_type=id_type)
        PersonIdentifier.objects.create(
            identifier='backslashes', person=person_record,
            person_identifier_type=id_type)
        PersonIdentifier.objects.create(
            identifier='profanely', person=person_record,
            person_identifier_type=id_type)
        # Then the full text field should reflect the changes
        self.assertIn(
            'emphatic',
            Person.objects.last().search_full_text
        )
        self.assertIn(
            'backslashes',
            Person.objects.last().search_full_text
        )
        self.assertIn(
            'profanely',
            Person.objects.last().search_full_text
        )


class PersonSearchAllFields(TestCase):
    def test_just_name(self):
        # Given there are some Person records in the system marked as law enforcement
        Person.objects.create(name="Chelsea Webster", is_law_enforcement=True)
        Person.objects.create(name="Maria E. Garcia", is_law_enforcement=True)
        Person.objects.create(name="Maria Celeste Ulberg Hansen", is_law_enforcement=True)
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)

        # When I call a query for one of their first names
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results = Person.objects.search_all_fields('Mohammed', user=admin_user)

        # Then I should only get back the one record containing that name, and not any of the other records
        self.assertEqual(
            1,
            len(results)
        )
        self.assertEqual(
            "Mohammed Alabbadi",
            results[0].name
        )

    def test_distinct_results(self):
        """Ensure that the there aren't duplicative results (typically caused by one-to-many joins & sorts)"""
        # Given there's one officer record in the system with multiple aliases and identifiers
        person_record = Person.objects.create(name="soothsayer", is_law_enforcement=True)
        PersonAlias.objects.create(name=f'forsooth', person=person_record)
        PersonAlias.objects.create(name=f'say', person=person_record)
        PersonAlias.objects.create(name=f'tooth', person=person_record)
        id_type = PersonIdentifierType.objects.create(name='Test Type')
        PersonIdentifier.objects.create(
            identifier='forsooth', person=person_record,
            person_identifier_type=id_type)
        PersonIdentifier.objects.create(
            identifier='say', person=person_record,
            person_identifier_type=id_type)
        PersonIdentifier.objects.create(
            identifier='tooth', person=person_record,
            person_identifier_type=id_type)

        # When I do a search that partially matches on the values of the aliases and identifiers
        admin_user = FdpUser.objects.create(is_administrator=True)
        results = Person.objects.search_all_fields('soothsayer', user=admin_user)

        # Then I should only see one result
        self.assertEqual(
            1,
            len(results),
            msg="More than one result returned for a single match"
        )

    def test_identifier_search_exact_match(self):
        # Given there are identifiers attached to a person record
        person_record = Person.objects.create(name="Test Person", is_law_enforcement=True)
        id_type = PersonIdentifierType.objects.create(name='Test Type')
        PersonIdentifier.objects.create(
            identifier='emphatic', person=person_record,
            person_identifier_type=id_type)
        PersonIdentifier.objects.create(
            identifier='backslashes', person=person_record,
            person_identifier_type=id_type)
        PersonIdentifier.objects.create(
            identifier='profanely', person=person_record,
            person_identifier_type=id_type)

        # When I do a search for one of them by exact string
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results = Person.objects.search_all_fields('backslashes', user=admin_user)

        # Then I should get back the record it is attached to
        self.assertEqual(
            person_record,
            results[0]
        )

    def test_aliases_search_exact_match(self):
        # Given there are identifiers attached to a person record
        person_record = Person.objects.create(name="Test Person", is_law_enforcement=True)
        id_type = PersonIdentifierType.objects.create(name='Test Type')
        PersonAlias.objects.create(name=f'taffeta', person=person_record)
        PersonAlias.objects.create(name=f'maggots', person=person_record)

        # When I do a search for one of them by exact string
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results = Person.objects.search_all_fields('taffeta', user=admin_user)

        # Then I should get back the record it is attached to
        self.assertEqual(
            person_record,
            results[0]
        )

    def test_num_queries(self):
        """Ensure that the method doesn't call more queries than intended
        """
        for _ in range(100):
            person_record = Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)
            PersonAlias.objects.create(name=f'Alias 1 for {person_record}', person=person_record)
            PersonAlias.objects.create(name=f'Alias 2 for {person_record}', person=person_record)

        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        with self.assertNumQueries(5):
            results = Person.objects.search_all_fields('Mohammed', user=admin_user)
            for result in results:
                list(result.person_aliases.all())
                list(result.person_titles.all())
                list(result.person_identifiers.all())

    def test_person_search_all_fields_discrimination(self):
        # Given there are some Person records in the system marked as law enforcement
        Person.objects.create(name="Chelsea Webster", is_law_enforcement=True)
        Person.objects.create(name="Maria E. Garcia", is_law_enforcement=True)
        Person.objects.create(name="Maria Celeste Ulberg Hansen", is_law_enforcement=True)
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)

        # When I call a query for one of their first names
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results = Person.objects.search_all_fields('Mohammed', user=admin_user)

        # Then I should only get back the one record containing that name, and not any of the other records
        self.assertEqual(
            1,
            len(results)
        )
        self.assertEqual(
            "Mohammed Alabbadi",
            results[0].name
        )

    def test_query_diacritic_folding(self):
        """Ensure that diacritic folding is happening to search query before search is performed
        """
        # Given there's a person record 'cafe' WITHOUT a diacritic mark in the name
        # and another record with a similar spelling off by one but EARLIER in alphabetical order
        person_record_match = Person.objects.create(name="cafe", is_law_enforcement=True)
        person_record_mismatch = Person.objects.create(name="cafa", is_law_enforcement=True)
        # When I do a search WITH a diacritic mark
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results = Person.objects.search_all_fields('café', user=admin_user)
        # Then the record named "cafe" should be first, not "cafa"
        self.assertEqual(
            "cafe",
            results[0].name
        )

    def test_access_controls_for_admin_only(self):
        # Given there is a record marked "admin only" in the system
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True,
                              for_admin_only=True)

        with self.subTest(msg="admin can see"):
            # When I call a query as an admin
            admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
            admin_results = Person.objects.search_all_fields('Mohammed Alabbadi', admin_user)

            # Then I should see the matching record in the results
            self.assertEqual(
                "Mohammed Alabbadi",
                admin_results[0].name
            )

        # When I call the same query as a non-admin user
        admin_user = FdpUser.objects.create(email='usertwo@localhost', is_administrator=False)
        non_admin_results = Person.objects.search_all_fields('Mohammed Alabbadi', admin_user)

        # Then I should NOT see the matching record in the results
        self.assertEqual(
            0,
            len(non_admin_results)
        )

    def test_access_controls_for_host_only(self):
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True,
                              for_host_only=True)

        with self.subTest(msg="admin can see"):
            host_admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True,
                                                     is_host=True)
            admin_results = Person.objects.search_all_fields("Mohammed Alabbadi", host_admin_user)

            self.assertEqual(
                "Mohammed Alabbadi",
                admin_results[0].name
            )

        guest_admin_user = FdpUser.objects.create(email='usertwo@localhost', is_administrator=False,
                                                  is_host=False)
        guest_admin_results = Person.objects.search_all_fields("Mohammed Alabbadi", guest_admin_user)

        # Then I should NOT see the matching record in the results
        self.assertEqual(
            0,
            len(guest_admin_results)
        )

    def test_access_controls_organization_only(self):
        organization = FdpOrganization.objects.create(name="unprophesiable")

        person_record = Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)
        person_record.fdp_organizations.add(organization)

        with self.subTest(msg="host end user can't see"):
            host_admin_user = FdpUser.objects.create(email='usertwo@localhost',
                                                     is_host=True)
            admin_results = Person.objects.search_all_fields("Mohammed Alabbadi", host_admin_user)
            self.assertEqual(
                0,
                admin_results.count()
            )

        with self.subTest(msg="org user can see"):
            org_admin_user = FdpUser.objects.create(email='userthree@localhost',
                                                    is_administrator=False,
                                                    fdp_organization=organization,
                                                    is_host=False)
            org_admin_results = Person.objects.search_all_fields("Mohammed Alabbadi", org_admin_user)

            # Then I should NOT see the matching record in the results
            self.assertEqual(
                1,
                len(org_admin_results)
            )

        # BTW
        with self.subTest(msg="host admin CAN see"):  # Too bad...
            host_admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True,
                                                     is_host=True)
            admin_results = Person.objects.search_all_fields("Mohammed Alabbadi", host_admin_user)
            self.assertEqual(
                1,
                admin_results.count()
            )

    def test_access_controls_for_admin_only_blank_search(self):
        # Given there is a record marked "admin only" in the system
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True,
                              for_admin_only=True)

        with self.subTest(msg="admin can see"):
            # When I call a query as an admin
            admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
            admin_results = Person.objects.search_all_fields('', admin_user)

            # Then I should see the matching record in the results
            self.assertEqual(
                "Mohammed Alabbadi",
                admin_results[0].name
            )

        # When I call the same query as a non-admin user
        admin_user = FdpUser.objects.create(email='usertwo@localhost', is_administrator=False)
        non_admin_results = Person.objects.search_all_fields('', admin_user)

        # Then I should NOT see the matching record in the results
        self.assertEqual(
            0,
            len(non_admin_results)
        )

    def test_access_controls_for_host_only_blank_search(self):
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True,
                              for_host_only=True)

        with self.subTest(msg="admin can see"):
            host_admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True,
                                                     is_host=True)
            admin_results = Person.objects.search_all_fields("", host_admin_user)

            self.assertEqual(
                "Mohammed Alabbadi",
                admin_results[0].name
            )

        guest_admin_user = FdpUser.objects.create(email='usertwo@localhost', is_administrator=False,
                                                  is_host=False)
        guest_admin_results = Person.objects.search_all_fields("", guest_admin_user)

        # Then I should NOT see the matching record in the results
        self.assertEqual(
            0,
            len(guest_admin_results)
        )

    def test_access_controls_organization_only_blank_search(self):
        organization = FdpOrganization.objects.create(name="unprophesiable")

        person_record = Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)
        person_record.fdp_organizations.add(organization)

        with self.subTest(msg="host end user can't see"):
            host_admin_user = FdpUser.objects.create(email='usertwo@localhost',
                                                     is_host=True)
            admin_results = Person.objects.search_all_fields("", host_admin_user)
            self.assertEqual(
                0,
                admin_results.count()
            )

        with self.subTest(msg="org user can see"):
            org_admin_user = FdpUser.objects.create(email='userthree@localhost',
                                                    is_administrator=False,
                                                    fdp_organization=organization,
                                                    is_host=False)
            org_admin_results = Person.objects.search_all_fields("", org_admin_user)

            # Then I should NOT see the matching record in the results
            self.assertEqual(
                1,
                len(org_admin_results)
            )

        # BTW
        with self.subTest(msg="host admin CAN see"):  # Too bad...
            host_admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True,
                                                     is_host=True)
            admin_results = Person.objects.search_all_fields("", host_admin_user)
            self.assertEqual(
                1,
                admin_results.count()
            )

    def test_access_is_law_enforcement(self):
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=False)

        with self.subTest(msg="admin can see"):
            host_admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
            admin_results = Person.objects.search_all_fields("Mohammed Alabbadi", host_admin_user)

            self.assertEqual(
                0,
                len(admin_results)
            )

        non_admin_user = FdpUser.objects.create(email='usertwo@localhost', is_administrator=False)
        non_admin_results = Person.objects.search_all_fields("Mohammed Alabbadi", non_admin_user)

        self.assertEqual(
            0,
            len(non_admin_results)
        )

    def test_middle_initials_ranking(self):
        # Given there are two "Roger Hobbes" records with one containing a middle initial
        Person.objects.create(name="Roger Hobbes", is_law_enforcement=True)
        Person.objects.create(name="Roger E. Hobbes", is_law_enforcement=True)
        # and there are six other officer records that start with "Roger"
        officer_names = [
            'Roger Bugaboo',
            'Roger Incrementally',
            'Roger Arturo',
            'Roger Confronters',
            'Roger Underlying',
            'Roger Acclimates',
        ]
        for officer_name in officer_names:
            Person.objects.create(name=officer_name, is_law_enforcement=True)

        # When I call a query for "Roger Hobbes"
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results = Person.objects.search_all_fields("Roger Hobbes", user=admin_user)

        # Then I should get back both "Roger Hobbes" and "Roger E. Hobbes" as the first two results
        self.assertEqual(
            "Roger Hobbes",
            results[0].name
        )
        self.assertEqual(
            "Roger E. Hobbes",
            results[1].name
        )
        # And I should get back all the records containing "Roger" in them (eight)
        self.assertEqual(
            8,
            len(results)
        )

    def test_subsorting(self):
        """Ensure that results with the same search rank are sorted logically"""
        # Given there are several officers with the same first name and same alias
        Person.objects.create(name="Andrew Y", is_law_enforcement=True)
        Person.objects.create(name="Andrew V", is_law_enforcement=True)
        Person.objects.create(name="Andrew U", is_law_enforcement=True)
        Person.objects.create(name="Andrew Z", is_law_enforcement=True)
        Person.objects.create(name="Andrew X", is_law_enforcement=True)
        Person.objects.create(name="Andrew Same", is_law_enforcement=True)
        Person.objects.create(name="Andrew Same", is_law_enforcement=True)
        Person.objects.create(name="Andrew Same", is_law_enforcement=True)
        Person.objects.create(name="Andrew Same", is_law_enforcement=True)
        Person.objects.create(name="Andrew Same", is_law_enforcement=True)
        for person_record in Person.objects.all():
            PersonAlias.objects.create(name='Same', person=person_record)
            person_record.save()

        # When I do a search just on the first name,
        # When I call a query for "Roger Hobbes"
        # with a query that doesn't match at all on any of the last names
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results_A = Person.objects.search_all_fields("Andrew same", user=admin_user)

        # And I perform the same search again
        results_B = Person.objects.search_all_fields("Andrew same", user=admin_user)
        results_C = Person.objects.search_all_fields("Andrew same", user=admin_user)
        results_D = Person.objects.search_all_fields("Andrew same", user=admin_user)

        # Then the results of the queries should be in the same order
        for i, person in enumerate(results_A):
            self.assertEqual(
                person.pk,
                results_C[i].pk
            )
            self.assertEqual(
                person.pk,
                results_B[i].pk
            )
            self.assertEqual(
                person.pk,
                results_D[i].pk
            )

    def test_check_variation_matches(self):
        things_to_check = [
            # {'source': "", 'query': "", 'scenario': ""},
            {'source': "Nicholas Agnoletti", 'query': "Nicholas", 'scenario': "query contains only first name"},
            {'source': "Nicholas Agnoletti", 'query': "Agnoletti", 'scenario': "query contains only last name"},
            {'source': "Nicholas Agnoletti", 'query': "Agnoletti Nicholas", 'scenario': "query reverses name order"},
            {'source': 'Jill Braaten', 'query': "Jill Braten", 'scenario': "spelling: missing repeated vowel in query"},
            {'source': "Joe O'Connell", 'query': "Joe OConnell",
             'scenario': "punctuation: apostrophe missing in query"},
            {'source': "Joe O'Connell", 'query': "Joe OConner",
             'scenario': "punctuation: apostrophe missing and misspelled in query"},
            {'source': "Joe O'Connell", 'query': "Joe O Connell",
             'scenario': "punctuation: apostrophe replaced with space in query"},
            {'source': "Roger E. Hobbes", 'query': "Roger Hobbes",
             'scenario': "middle names: middle initial missing from query"},
            {'source': "Jane Alreyashi-Watson", 'query': "Jane Alreyashi Watson",
             'scenario': "punctuation: hyphen replaced with space in query"},
            {'source': "Jane Alreyashi Watson", 'query': "Jane Alreyashi-Watson",
             'scenario': "punctuation: hyphen replaced with space in source"},
            {'source': "Jane AlreyashiWatson", 'query': "Jane Alreyashi-Watson",
             'scenario': 'punctuation: hyphen missing in source'},
        ]

        for thing in things_to_check:
            with self.subTest(msg=str(thing)):
                with transaction.atomic():  # Maintain test isolation
                    # Given there's an officer with the name...
                    Person.objects.create(name=thing['source'], is_law_enforcement=True)
                    # When I call search_all_fields for...
                    admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
                    results = Person.objects.search_all_fields(thing['query'], user=admin_user)
                    # Then I should see the record returned
                    self.assertEqual(
                        1,
                        len(results)
                    )
                    self.assertEqual(
                        thing['source'],
                        results[0].name
                    )
                    transaction.set_rollback(True)  # Maintain test isolation
