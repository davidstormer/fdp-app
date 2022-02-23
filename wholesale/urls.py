from django.urls import path, re_path
from django.conf import settings
from inheritable.models import AbstractUrlValidator
from . import views


app_name = 'wholesale'


urlpatterns = [
    re_path(
        r'{b}{s}(?P<path>.*)'.format(
            b=settings.FDP_MEDIA_URL[1:] if settings.FDP_MEDIA_URL.startswith('/') else settings.FDP_MEDIA_URL,
            s=AbstractUrlValidator.WHOLESALE_BASE_URL
        ),
        view=views.DownloadWholesaleImportFileView.as_view(),
        name='download_import_file'
    ),
    path(AbstractUrlValidator.WHOLESALE_HOME_URL, views.IndexTemplateView.as_view(), name='index'),
    path(AbstractUrlValidator.WHOLESALE_TEMPLATE_URL, views.TemplateFormView.as_view(), name='template'),
    path(AbstractUrlValidator.WHOLESALE_CREATE_IMPORT_URL,
         views.CreateImportCreateView.as_view(), name='create_import'),
    path(f'{AbstractUrlValidator.WHOLESALE_START_IMPORT_URL}<int:pk>/',
         views.StartImportFormView.as_view(), name='start_import'),
    path(f'{AbstractUrlValidator.WHOLESALE_LOG_URL}<int:pk>/', views.ImportLogListView.as_view(), name='log'),
    path(AbstractUrlValidator.WHOLESALE_LOGS_URL, views.ImportLogsListView.as_view(), name='logs'),
]
