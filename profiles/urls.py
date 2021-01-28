from django.urls import path
from inheritable.models import AbstractUrlValidator
from . import views


app_name = 'profiles'


urlpatterns = [
    path('', views.IndexTemplateView.as_view(), name='index'),
    path(AbstractUrlValidator.OFFICER_SEARCH_URL, views.OfficerSearchFormView.as_view(), name='officer_search'),
    path(
        AbstractUrlValidator.OFFICER_SEARCH_RESULTS_URL,
        views.OfficerSearchResultsListView.as_view(),
        name='officer_search_results'
    ),
    path('{u}<int:pk>'.format(u=AbstractUrlValidator.OFFICER_URL), views.OfficerDetailView.as_view(), name='officer'),
    path(
        '{u}<int:pk>'.format(u=AbstractUrlValidator.OFFICER_DOWNLOAD_ALL_FILES_URL),
        views.OfficerDownloadAllFilesView.as_view(),
        name='officer_download_all_files'
    ),
    path(AbstractUrlValidator.COMMAND_SEARCH_URL, views.CommandSearchFormView.as_view(), name='command_search'),
    path(
        AbstractUrlValidator.COMMAND_SEARCH_RESULTS_URL,
        views.CommandSearchResultsListView.as_view(),
        name='command_search_results'
    ),
    path('{u}<int:pk>'.format(u=AbstractUrlValidator.COMMAND_URL), views.CommandDetailView.as_view(), name='command'),
    path(
        '{u}<int:pk>'.format(u=AbstractUrlValidator.COMMAND_DOWNLOAD_ALL_FILES_URL),
        views.CommandDownloadAllFilesView.as_view(),
        name='command_download_all_files'
    )
]
