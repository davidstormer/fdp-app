from core.models import Person
from functional_tests.common import FunctionalTestCase
from profiles.models import SiteSetting


class CustomTextBlocks(FunctionalTestCase):
    """Use FunctionalTestCase as a lightweight alternative to SeleniumFunctionalTestCase when JavaScript and styling
    do not need to be accounted for.
    """

    def test_text_on_profile_top(self):
        # Given there's a site setting 'profile_text_above'
        SiteSetting.objects.create(
            key='profile_text_above',
            value='certifying dynamite'
        )
        # When I go to an officer profile page
        officer_record = Person.objects.create(is_law_enforcement=True, name="Test Officer")
        admin_client = self.log_in(is_administrator=False)
        response = admin_client.get(officer_record.get_profile_url, follow=True)

        # Then I should see the text printed at the top of the page
        self.assertContains(
            response,
            'certifying dynamite',
        )
