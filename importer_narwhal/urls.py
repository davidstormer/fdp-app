from django.urls import path

from . import views

app_name = 'importer_narwhal'

urlpatterns = [
    path('', views.BatchListingLandingView.as_view(), name="importer-landing"),
    path('batch/<int:pk>', views.ImportBatchDetailView.as_view(), name="batch"),
    path('batch/<int:pk>/dry-run-report', views.StartDryRun.as_view(), name="dry-run-report"),
    path('batch/<int:pk>/records', views.RunImportBatch.as_view(), name="records"),
    path('batch/new', views.ImportBatchCreateView.as_view(), name="new-batch"),
]
