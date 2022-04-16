from django.db import transaction
from django.test import TestCase
from core.models import Person


class PersonSearchByName(TestCase):
    def test_person_search_by_name_descrimination(self):
        # Given there are some Person records in the system marked as law enforcement
        Person.objects.create(name="Chelsea Webster", is_law_enforcement=True)
        Person.objects.create(name="Maria E Garcia", is_law_enforcement=True)
        Person.objects.create(name="Maria Celeste Ulberg Hansen", is_law_enforcement=True)
        Person.objects.create(name="Mohammed Alabbadi", is_law_enforcement=True)

        # When I call a query for one of their first names
        results = Person.objects.search_by_name('Mohammed')

        # Then I should only get back the one record containing that name, and not any of the other records
        self.assertEqual(
            1,
            len(results)
        )
        self.assertEqual(
            "Mohammed Alabbadi",
            results[0].name
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
        results = Person.objects.search_by_name("Roger Hobbes")

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
                    Person.objects.create(name=thing['source'])
                    # When I call search_by_name for...
                    results = Person.objects.search_by_name(thing['query'])
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
