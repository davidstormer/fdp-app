from django import forms
from django.conf import settings
from django.utils.translation import gettext as _

from profiles.common import CUSTOM_TEXT_ALLOWED_TAGS


class OfficerSearchForm(forms.Form):
    """ Synchronous form to search for officers.

    Fields:
        search (str): Free-text search criteria.

    """
    search = forms.CharField(
        label=_('Search'),
        max_length=settings.MAX_NAME_LEN,
        help_text=_('Search by names, IDs, keywords and more')
    )


class CommandSearchForm(forms.Form):
    """ Synchronous form to search for commands.

    Fields:
        search (str): Free-text search criteria.

    """
    search = forms.CharField(
        label=_('Search'),
        max_length=settings.MAX_NAME_LEN,
        help_text=_('Search by name or abbreviation')
    )


class SiteSettingsForm(forms.Form):

    officer_profile_page_top = forms.CharField(
        widget=forms.Textarea,
        help_text=f"This text will appear at the top of the officer and command profile pages. Allowed HTML tags: "
                  f"{', '.join(CUSTOM_TEXT_ALLOWED_TAGS)}.",
        required=False
    )

    officer_profile_incidents = forms.CharField(
        widget=forms.Textarea,
        help_text=f"This text will appear at the top of the incidents section of officer profile pages. Allowed HTML "
                  f"tags: {', '.join(CUSTOM_TEXT_ALLOWED_TAGS)}.",
        required=False
    )
