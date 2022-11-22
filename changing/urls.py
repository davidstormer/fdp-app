from django.urls import path, re_path
from inheritable.models import AbstractUrlValidator
from . import views
from .forms import WizardSearchForm


app_name = 'changing'


urlpatterns = [
    path(AbstractUrlValidator.CHANGING_HOME_URL, views.IndexTemplateView.as_view(), name='index'),
    # searches and search results
    path(AbstractUrlValidator.CHANGING_CONTENT_URL, views.ContentWizardSearchFormView.as_view(), name='content'),
    path(AbstractUrlValidator.CHANGING_INCIDENTS_URL, views.IncidentWizardSearchFormView.as_view(), name='incidents'),
    path(AbstractUrlValidator.CHANGING_PERSONS_URL, views.PersonWizardSearchFormView.as_view(), name='persons'),
    path(AbstractUrlValidator.CHANGING_GROUPINGS_URL, views.GroupingWizardSearchFormView.as_view(), name='groupings'),
    re_path(r'{u}(?P<type>{c}|{i}|{p}|{g})/'.format(
        u=AbstractUrlValidator.CHANGING_SEARCH_RESULTS_URL,
        c=WizardSearchForm.content_type,
        i=WizardSearchForm.incident_type,
        p=WizardSearchForm.person_type,
        g=WizardSearchForm.grouping_type
    ), views.WizardSearchResultsTemplateView.as_view(), name='list'),
    # grouping data wizard forms
    path(AbstractUrlValidator.ADD_GROUPING_URL, views.GroupingCreateView.as_view(), name='add_grouping'),
    path('{u}<int:pk>/'.format(u=AbstractUrlValidator.EDIT_GROUPING_URL),
         views.GroupingUpdateView.as_view(), name='edit_grouping'),
    path(AbstractUrlValidator.ASYNC_GET_GROUPINGS_URL,
         views.AsyncGetGroupingsView.as_view(), name='async_get_groupings'),
    # person data wizard forms
    path(AbstractUrlValidator.ADD_PERSON_URL, views.PersonCreateView.as_view(), name='add_person'),
    path('{u}<int:pk>/'.format(u=AbstractUrlValidator.EDIT_PERSON_URL),
         views.PersonUpdateView.as_view(), name='edit_person'),
    path(AbstractUrlValidator.ASYNC_GET_PERSONS_URL,
         views.AsyncGetPersonsView.as_view(), name='async_get_persons'),
    # incident data wizard forms
    path(AbstractUrlValidator.ADD_INCIDENT_URL, views.IncidentCreateView.as_view(), name='add_incident'),
    path('{u}<int:pk>/<int:content_id>/'.format(u=AbstractUrlValidator.EDIT_INCIDENT_URL),
         views.IncidentUpdateView.as_view(), name='edit_incident'),
    path(AbstractUrlValidator.ADD_LOCATION_URL,
         views.LocationCreateView.as_view(), name='add_location'),
    # closing data wizard popup forms
    path('{u}<slug:popup_id>/<str:str_rep>/<int:pk>/'.format(u=AbstractUrlValidator.CHANGING_CLOSE_POPUP_URL),
         views.ClosePopupTemplateView.as_view(), name='close_popup'),
    # content data wizard forms
    path(AbstractUrlValidator.ADD_CONTENT_URL, views.ContentCreateView.as_view(), name='add_content'),
    path('{u}<int:pk>/'.format(u=AbstractUrlValidator.EDIT_CONTENT_URL),
         views.ContentUpdateView.as_view(), name='edit_content'),
    path(AbstractUrlValidator.ASYNC_GET_ATTACHMENTS_URL,
         views.AsyncGetAttachmentsView.as_view(), name='async_get_attachments'),
    path(AbstractUrlValidator.ADD_ATTACHMENT_URL,
         views.AttachmentCreateView.as_view(), name='add_attachment'),
    path(AbstractUrlValidator.ASYNC_GET_INCIDENTS_URL,
         views.AsyncGetIncidentsView.as_view(), name='async_get_incidents'),
    path('{u}<int:pk>/'.format(u=AbstractUrlValidator.LINK_ALLEGATIONS_PENALTIES_URL),
         views.AllegationPenaltyLinkUpdateView.as_view(), name='link_allegations_penalties'),
]
