from django.urls import path

from . import views

app_name = 'importer_narwhal'

urlpatterns = [
    path('batch/<int:pk>', views.ImportBatchDetailView.as_view(), name="batch"),
]
