from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit
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

    profile_page_top = forms.CharField(
        widget=forms.Textarea,
        help_text=f"This text will appear at the top of the officer and command profile pages. (Allowed HTML tags: "
                  f"{', '.join(CUSTOM_TEXT_ALLOWED_TAGS)})",
        required=False
    )

    profile_incidents = forms.CharField(
        widget=forms.Textarea,
        help_text=f"This text will appear at the top of the incidents section of officer profile pages. (Allowed HTML "
                  f"tags: {', '.join(CUSTOM_TEXT_ALLOWED_TAGS)})",
        required=False
    )

    global_footer = forms.CharField(
        widget=forms.Textarea,
        help_text=f"This text will appear at the bottom of every page, including the home page. (Allowed HTML "
                  f"tags: {', '.join(CUSTOM_TEXT_ALLOWED_TAGS)})",
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-10'
        self.helper.wrapper_class = 'mb-5'
        self.helper.layout = Layout(
            Fieldset(
                'Custom text blocks',
                'profile_page_top',
                'profile_incidents',
                'global_footer',
                FormActions(
                    Submit('save', 'Save'),
                ),
                css_class='mt-4'
            )
        )
