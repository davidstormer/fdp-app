from django.test import TestCase
from core.models import Person


class PersonSearch(TestCase):
    def test_person_search_by_name(self):
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
