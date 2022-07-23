from django.test import TestCase
from core.models import Person
from functional_tests.common import FunctionalTestCase, SeleniumFunctionalTestCase, wait


class SnapshotFeatureToggleTests(FunctionalTestCase):

    def test_snapshot_feature_toggle_disabled(self):
        # Given the SNAPSHOT_DISABLE settings is = True
        with self.settings(SNAPSHOT_DISABLE = True):

            # When I go to an officer profile page
            person_record = Person.objects.create(name="Test Person", is_law_enforcement=True)
            admin_client = self.log_in(is_administrator=True)
            response_admin_client = admin_client.get(f'/officer/{person_record.pk}', follow=True)

            # Then I should NOT see a snapshot section
            self.assertNotContains(
                response_admin_client,
                'Snapshot'
            )

    def test_snapshot_feature_toggle_enabled(self):
        # Given the SNAPSHOT_DISABLE settings is = False
        with self.settings(SNAPSHOT_DISABLE = False):

            # When I go to an officer profile page
            person_record = Person.objects.create(name="Test Person", is_law_enforcement=True)
            admin_client = self.log_in(is_administrator=True)
            response_admin_client = admin_client.get(f'/officer/{person_record.pk}', follow=True)

            # Then I should NOT see a snapshot section
            self.assertContains(
                response_admin_client,
                'Snapshot'
            )
