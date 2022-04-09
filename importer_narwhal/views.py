from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.generic import DetailView, CreateView

from importer_narwhal.models import ImportBatch


class ImportBatchCreateView(CreateView):

    model = ImportBatch
    fields = ['target_model_name', 'import_sheet']


class ImportBatchDetailView(DetailView):

    model = ImportBatch

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Import batch: {context['object'].pk}"

        page_number = self.request.GET.get('page')
        imported_rows_paginator = Paginator(
            context['object'].imported_rows.all().order_by('row_number').values(), 100)
        error_rows_paginator = Paginator(
            context['object'].error_rows.all().order_by('row_number').values(), 100)
        context['error_rows_paginated'] = error_rows_paginator.get_page(page_number or 1)
        context['imported_rows_paginated'] = imported_rows_paginator.get_page(page_number or 1)
        context['page_obj'] = context['error_rows_paginated'] or context['imported_rows_paginated']
        return context
