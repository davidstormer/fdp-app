from django import forms
from django.conf import settings
from django.utils.translation import gettext as _


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

    profile_text_above = forms.CharField(
        widget=forms.Textarea,
        help_text="This text will appear at the top of the officer and command profile pages."
    )
