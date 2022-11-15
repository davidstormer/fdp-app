from django.urls import path

from . import views

app_name = 'importer_narwhal'

urlpatterns = [
    path('do-a-think', views.TestMakePersonsView.as_view(), name="do-a-think"),
    path('', views.BatchListingLandingView.as_view(), name="importer-landing"),
    path('mappings', views.MappingsView.as_view(), name="importer-mappings"),
    path('batch/<int:pk>', views.ImportBatchDetailView.as_view(), name="batch"),
    path('batch/<int:pk>/dry-run-report', views.StartDryRun.as_view(), name="dry-run-report"),
    path('batch/<int:pk>/records', views.RunImportBatch.as_view(), name="records"),
    path('batch/new', views.ImportBatchCreateView.as_view(), name="new-batch"),
]
