from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, CreateView, ListView

from importer_narwhal.models import ImportBatch
from importer_narwhal.narwhal import do_dry_run, run_import_batch, resource_model_mapping

from inheritable.views import HostAdminSyncTemplateView


class MappingsView(HostAdminSyncTemplateView):
    template_name = 'importer_narwhal/mappings.html'

    def get_context_data(self, **kwargs):
        context = super(MappingsView, self).get_context_data(**kwargs)
        context.update({
            'title': 'Importer Mappings',
            'mappings': resource_model_mapping,
        })
        return context


class BatchListingLandingView(ListView):
    model = ImportBatch
    paginate_by = 25
    queryset = ImportBatch.objects.all().order_by('-pk')


class ImportBatchCreateView(CreateView):

    model = ImportBatch
    fields = ['target_model_name', 'import_sheet']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Import batch setup'
        context['stepper_number'] = 1
        return context


class StartDryRun(View):

    def post(self, request, *args, **kwargs):
        batch = ImportBatch.objects.get(pk=kwargs['pk'])
        do_dry_run(batch)
        return redirect(reverse('importer_narwhal:batch', kwargs={'pk': kwargs['pk']}))


class RunImportBatch(View):

    def post(self, request, *args, **kwargs):
        batch = ImportBatch.objects.get(pk=kwargs['pk'])
        run_import_batch(batch)
        return redirect(reverse('importer_narwhal:batch', kwargs={'pk': kwargs['pk']})
                        + '?show_workflow_after_completion=true')


class ImportBatchDetailView(DetailView):

    model = ImportBatch

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Import batch: {context['object'].pk}"

        # Workflow state

        # 'pre-validate' Batch newly created, ready to verify
        #   highlight "Validate" in stepper
        #   show button to verify
        if not context['object'].dry_run_started:
            context['state'] = 'pre-validate'
            context['stepper_number'] = 2

        # 'mid-validate' Currently running validation
        #   highlight "Validate" in stepper
        #   say we're in the middle of validation; show spinner
        #   don't show button to import
        elif context['object'].dry_run_started \
                and not context['object'].dry_run_completed:
            context['state'] = 'mid-validate'
            context['stepper_number'] = 2

        # 'post-validate-errors' Batch verified, problems, abort
        #   highlight "Validate" in stepper
        #   don't show button to import
        elif context['object'].dry_run_completed \
                and context['object'].errors_encountered:
            context['state'] = 'post-validate-errors'
            context['stepper_number'] = 2

        # 'post-validate-ready' Batch verified, no errors, ready to import
        #   highlight "Import" in stepper
        #   show button to import
        elif context['object'].dry_run_completed \
                and not context['object'].errors_encountered \
                and not context['object'].started:
            context['state'] = 'post-validate-ready'
            context['stepper_number'] = 3

        # 'mid-import' Currently running import
        #   highlight "Import" in stepper
        #   say we're in the middle of importing; show spinner
        #   don't show button to import
        elif context['object'].started and not context['object'].completed:
            context['state'] = 'mid-import'
            context['stepper_number'] = 3

        # 'post-import' Batch imported, done! (todo: show button to delete)
        #   keep showing stepper (last time)
        #   highlight "Review" in stepper
        #   don't show button to import
        elif context['object'].completed and self.request.GET.get('show_workflow_after_completion'):
            context['state'] = 'complete'
            context['stepper_number'] = 4

        # 'post-import' Batch imported, done! (todo: show button to delete)
        #   don't show stepper anymore (I'm viewing it outside of the workflow)
        #   don't show button to import
        elif context['object'].completed:
            context['state'] = 'done'
            context['stepper_number'] = 4

        # Pagination
        page_number = self.request.GET.get('page')
        imported_rows_paginator = Paginator(
            context['object'].imported_rows.all().order_by('row_number').values(), 100)
        error_rows_paginator = Paginator(
            context['object'].error_rows.all().order_by('row_number').values(), 100)
        context['error_rows_paginated'] = error_rows_paginator.get_page(page_number or 1)
        context['imported_rows_paginated'] = imported_rows_paginator.get_page(page_number or 1)
        context['page_obj'] = context['error_rows_paginated'] or context['imported_rows_paginated']

        return context
