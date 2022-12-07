from django.urls import path

from . import views

app_name = 'importer_narwhal'

urlpatterns = [
    path('', views.BatchListingLandingView.as_view(), name="importer-landing"),
    path('mappings', views.MappingsView.as_view(), name="importer-mappings"),
    path('batch/<int:pk>', views.ImportBatchDetailView.as_view(), name="batch"),
    path('batch/<int:pk>/dry-run-report', views.StartDryRun.as_view(), name="dry-run-report"),
    path('batch/<int:pk>/records', views.RunImportBatch.as_view(), name="records"),
    path('batch/new', views.ImportBatchCreateView.as_view(), name="new-batch"),
    path('exports/', views.ExporterLandingView.as_view(), name="exporter-landing"),
    path('exports/<int:pk>', views.ExportBatchDetailView.as_view(), name="exporter-batch"),
    path('exports/<int:pk>/download', views.DownloadExportFileView.as_view(), name="exporter-batch-download"),
    path('exports/new', views.ExportBatchCreateView.as_view(), name="exporter-new-batch"),
]
