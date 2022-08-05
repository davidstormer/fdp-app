from functional_tests.common import FunctionalTestCase
from supporting.models import PersonRelationshipType


class UpdateRelationshipTypesSelenium(FunctionalTestCase):
    def test_relationship_types_new_shows_on_changing_page(self):
        # Given a new relationship type has been added to the system
        PersonRelationshipType.objects.create(name="beryllium")

        # When I go to the person edit page
        admin_client = self.log_in(is_administrator=True)
        response_admin_client = admin_client.get('/changing/persons/add/person/', follow=True)

        # Then the new type should be on the list of options in the relationship type select list
        self.assertContains(
            response_admin_client,
            'beryllium'
        )
