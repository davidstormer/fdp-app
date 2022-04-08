from django.shortcuts import render
from django.views.generic import DetailView

from importer_narwhal.models import ImportBatch


class ImportBatchDetailView(DetailView):

    model = ImportBatch

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Import batch: {context['object'].pk}"
        return context
