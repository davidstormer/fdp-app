from unittest import skip

from django.db import transaction
from django.test import TestCase
from core.models import Person, PersonAlias, PersonIdentifier
from fdpuser.models import FdpUser
from supporting.models import PersonIdentifierType


class FullTextIndexing(TestCase):
    def test_repopulate_util_full_text_name(self):
        # Given there's a Person record
        person_record = Person.objects.create(name="echinodermal")
        # Then the full text field should reflect the changes
        self.assertIn(
            'echinodermal',
            Person.objects.last().util_full_text
        )

# def test_repopulate_util_full_text_name(self):
#     # Given there's a Person record
#     person_record = Person.objects.create(name="Test Person")
#     # When I update the identifiers for the person
#     PersonIdentifier.objects.create(identifier='echinodermal', person=person_record,
#                                     person_identifier_type=PersonIdentifierType.objects.create(name='Test Type'))
#     # Then the full text field should reflect the changes
#     self.assertIn(
#         'echinodermal',
#         Person.objects.last().util_full_text
#     )


class PersonSearchAllFields(TestCase):
    def test_search_all_fields_num_queries(self):
        """Ensure that the method doesn't call more queries than intended
        """
        for _ in range(100):
            person_record = Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)
            PersonAlias.objects.create(name=f'Alias 1 for {person_record}', person=person_record)
            PersonAlias.objects.create(name=f'Alias 2 for {person_record}', person=person_record)

        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        with self.assertNumQueries(4):
            results = Person.objects.search_all_fields('Mohammed', user=admin_user)
            for result in results:
                list(result.person_aliases.all())
                list(result.person_titles.all())
                list(result.person_identifiers.all())


class PersonSearchByName(TestCase):
    def test_person_search_by_name_discrimination(self):
        # Given there are some Person records in the system marked as law enforcement
        Person.objects.create(name="Chelsea Webster", is_law_enforcement=True)
        Person.objects.create(name="Maria E. Garcia", is_law_enforcement=True)
        Person.objects.create(name="Maria Celeste Ulberg Hansen", is_law_enforcement=True)
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)

        # When I call a query for one of their first names
        admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
        results = Person.objects.search_by_name('Mohammed', user=admin_user)

        # Then I should only get back the one record containing that name, and not any of the other records
        self.assertEqual(
            1,
            len(results)
        )
        self.assertEqual(
            "Mohammed Alabbadi",
            results[0].name
        )

    def test_access_controls_for_admin_only(self):
        # Given there is a record marked "admin only" in the system
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True,
                              for_admin_only=True)

        with self.subTest(msg="admin can see"):
            # When I call a query as an admin
            admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
            admin_results = Person.objects.search_by_name('Mohammed Alabbadi', admin_user)

            # Then I should see the matching record in the results
            self.assertEqual(
                "Mohammed Alabbadi",
                admin_results[0].name
            )

        # When I call the same query as a non-admin user
        admin_user = FdpUser.objects.create(email='usertwo@localhost',is_administrator=False)
        non_admin_results = Person.objects.search_by_name('Mohammed Alabbadi', admin_user)

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
            admin_results = Person.objects.search_by_name("Mohammed Alabbadi", host_admin_user)

            self.assertEqual(
                "Mohammed Alabbadi",
                admin_results[0].name
            )

        guest_admin_user = FdpUser.objects.create(email='usertwo@localhost', is_administrator=False,
                                                  is_host=False)
        guest_admin_results = Person.objects.search_by_name("Mohammed Alabbadi", guest_admin_user)

        # Then I should NOT see the matching record in the results
        self.assertEqual(
            0,
            len(guest_admin_results)
        )

    def test_access_is_law_enforcement(self):
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=False)

        with self.subTest(msg="admin can see"):
            host_admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
            admin_results = Person.objects.search_by_name("Mohammed Alabbadi", host_admin_user)

            self.assertEqual(
                0,
                len(admin_results)
            )

        non_admin_user = FdpUser.objects.create(email='usertwo@localhost', is_administrator=False)
        non_admin_results = Person.objects.search_by_name("Mohammed Alabbadi", non_admin_user)

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
        results = Person.objects.search_by_name("Roger Hobbes", user=admin_user)

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

    def test_check_variation_matches(self):
        things_to_check = [
            # {'source': "", 'query': "", 'scenario': ""},
            {'source': "Nicholas Agnoletti", 'query': "Nicholas", 'scenario': "query contains only first name"},
            {'source': "Nicholas Agnoletti", 'query': "Agnoletti", 'scenario': "query contains only last name"},
            {'source': "Nicholas Agnoletti", 'query': "Agnoletti Nicholas", 'scenario': "query reverses name order"},
            {'source': 'Jill Braaten', 'query': "Jill Braten", 'scenario': "spelling: missing repeated vowel in query"},
            {'source': "Joe O'Connell", 'query': "Joe OConnell", 'scenario': "punctuation: apostrophe missing in query"},
            {'source': "Joe O'Connell", 'query': "Joe OConner", 'scenario': "punctuation: apostrophe missing and misspelled in query"},
            {'source': "Joe O'Connell", 'query': "Joe O Connell", 'scenario': "punctuation: apostrophe replaced with space in query"},
            {'source': "Roger E. Hobbes", 'query': "Roger Hobbes", 'scenario': "middle names: middle initial missing from query"},
            {'source': "Jane Alreyashi-Watson", 'query': "Jane Alreyashi Watson", 'scenario': "punctuation: hyphen replaced with space in query"},
            {'source': "Jane Alreyashi Watson", 'query': "Jane Alreyashi-Watson", 'scenario': "punctuation: hyphen replaced with space in source"},
            {'source': "Jane AlreyashiWatson", 'query': "Jane Alreyashi-Watson", 'scenario': 'punctuation: hyphen missing in source'},
        ]

        for thing in things_to_check:
            with self.subTest(msg=str(thing)):
                with transaction.atomic():  # Maintain test isolation
                    # Given there's an officer with the name...
                    Person.objects.create(name=thing['source'], is_law_enforcement=True)
                    # When I call search_by_name for...
                    admin_user = FdpUser.objects.create(email='userone@localhost', is_administrator=True)
                    results = Person.objects.search_by_name(thing['query'], user=admin_user)
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
