from timeit import timeit

from functional_tests.common import FunctionalTestCase
from core.models import Grouping, Person, PersonGrouping
from django.test import tag


class CommandProfilePerformance(FunctionalTestCase):
    @tag('wip')
    def test_view_num_queries_invariant(self):
        command = Grouping.objects.create(name="Test Command", is_law_enforcement=True)
        for i in range(150):
            PersonGrouping.objects.create(
                grouping=command,
                person=Person.objects.create(name=f"Test Person sacculation {i}", is_law_enforcement=True)
            )

        for i in range(150):
            PersonGrouping.objects.create(
                grouping=command,
                person=Person.objects.create(
                    name=f"Test Person no longer Koschei {i}",
                    is_law_enforcement=True
                ),
                ended_unknown_date=True
            )

        admin_client = self.log_in(is_administrator=True)
        with self.assertNumQueries(31):
            response = admin_client.get(f'/command/{command.pk}', follow=True)

        self.assertContains(response, 'sacculation')
        self.assertContains(response, 'Koschei')

    @tag('wip')
    def test_view_run_time(self):
        command = Grouping.objects.create(name="Test Command", is_law_enforcement=True)
        for i in range(300):
            PersonGrouping.objects.create(
                grouping=command,
                person=Person.objects.create(name=f"Test Person sacculation {i}", is_law_enforcement=True)
            )

        for i in range(300):
            PersonGrouping.objects.create(
                grouping=command,
                person=Person.objects.create(
                    name=f"Test Person no longer Koschei {i}",
                    is_law_enforcement=True
                ),
                ended_unknown_date=True
            )

        admin_client = self.log_in(is_administrator=True)

        def call_export():
            response = admin_client.get(f'/command/{command.pk}', follow=True)

        run_time = timeit(call_export, number=1)

        print(f"run_time: {run_time}")
        self.assertLessEqual(
            run_time,
            1,
            msg="Page load took longer than one second!"
        )
