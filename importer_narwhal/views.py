import os
import tempfile
from pathlib import Path
from zipfile import ZipFile

import kombu
from django.contrib import messages
from django.utils import timezone
import tablib
from django import forms
from django.core.files import File
from django.core.paginator import Paginator
from django.forms import MultipleChoiceField
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, CreateView, ListView
from tablib import Dataset

from fdp import settings
from importer_narwhal.models import ImportBatch, ExportBatch, MODEL_ALLOW_LIST
from importer_narwhal.narwhal import do_dry_run, run_import_batch, resource_model_mapping, do_export, run_export_batch
from inheritable.models import AbstractUrlValidator, AbstractConfiguration
from importer_narwhal.celerytasks import background_do_dry_run, celery_app, background_run_import_batch, \
    background_run_export_batch

from inheritable.views import HostAdminSyncTemplateView, HostAdminSyncListView, HostAdminSyncDetailView, \
    HostAdminAccessMixin, HostAdminSyncCreateView, SecuredSyncView, HostAdminSyncView


class MappingsView(HostAdminSyncTemplateView):
    template_name = 'importer_narwhal/mappings.html'

    def get_context_data(self, **kwargs):
        context = super(MappingsView, self).get_context_data(**kwargs)
        context.update({
            'title': 'Importer Mappings',
            'mappings': resource_model_mapping,
        })
        return context


class BatchListingLandingView(HostAdminSyncListView):
    model = ImportBatch
    paginate_by = 25
    queryset = ImportBatch.objects.all().order_by('-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Importer'
        return context


class ImportBatchCreateView(HostAdminSyncCreateView):

    model = ImportBatch
    fields = ['import_sheet', 'target_model_name']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Import batch setup'
        context['stepper_number'] = 1
        return context


def try_celery_task_or_fallback_to_synchronous_call(
        celery_task,
        fallback_function,
        batch_record: ImportBatch or ExportBatch,
        request):
    try:
        celery_ping_result = celery_app.control.ping()  # Make sure that Celery is configured and working
        if celery_ping_result:
            celery_task = celery_task.delay(batch_record.pk)
        else:
            raise Exception("No Celery workers found. Is the Celery daemon running?")
    except kombu.exceptions.OperationalError as e:
        messages.add_message(
            request,
            messages.WARNING,
            f'\'Celery\' background tasks misconfigured or missing. Falling back to synchronous mode. Long '
            f'running imports may fail quietly. Contact your systems administrator to address this issue. Message '
            f'broker unavailable: "{e}"'
        )
        fallback_function(batch_record)
    except Exception as e:
        messages.add_message(
            request,
            messages.WARNING,
            f'\'Celery\' background tasks misconfigured or missing. Falling back to synchronous mode. Long '
            f'running imports may fail quietly. Contact your systems administrator to address this issue. "{e}"'
        )
        fallback_function(batch_record)


class StartDryRun(HostAdminAccessMixin, View):

    def post(self, request, *args, **kwargs):
        # Record a provisional start time; this will be overwritten by do_dry_run().
        batch_record = ImportBatch.objects.get(pk=kwargs['pk'])
        batch_record.dry_run_started = timezone.now()
        batch_record.save()
        try_celery_task_or_fallback_to_synchronous_call(
            background_do_dry_run,
            do_dry_run,
            batch_record,
            self.request
        )
        return redirect(reverse('importer_narwhal:batch', kwargs={'pk': kwargs['pk']}))


class RunImportBatch(HostAdminAccessMixin, View):

    def post(self, request, *args, **kwargs):
        # Record a provisional start time; this will be overwritten by run_import_batch().
        batch_record = ImportBatch.objects.get(pk=kwargs['pk'])
        batch_record.started = timezone.now()
        batch_record.save()
        try_celery_task_or_fallback_to_synchronous_call(
            background_run_import_batch,
            run_import_batch,
            batch_record,
            self.request
        )
        return redirect(reverse('importer_narwhal:batch', kwargs={'pk': kwargs['pk']})
                        + '?show_workflow_after_completion=true')


class ImportBatchDetailView(HostAdminSyncDetailView):

    model = ImportBatch

    def get_template_names(self):
        context = self.get_context_data()
        if context['state'] == 'pre-validate':
            return f"importbatch_detail_pre-validate.html"
        elif context['state'] == "mid-validate":
            return f"importbatch_detail_mid-validate.html"
        elif context['state'] == "post-validate-errors":
            return f"importbatch_detail_post-validate-errors.html"
        elif context['state'] == "post-validate-ready":
            return f"importbatch_detail_post-validate-ready.html"
        elif context['state'] == "mid-import":
            return f"importbatch_detail_mid-import.html"
        elif context['state'] == "post-import-failed":
            return f"importbatch_detail_post-import-failed.html"
        elif context['state'] == "complete":
            return f"importbatch_detail_complete.html"
        else:
            return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Import batch: {context['object'].pk}"

        stepper_states = {
            'pre-validate': 2,
            'mid-validate': 2,
            'post-validate-errors': 2,
            'post-validate-ready': 3,
            'mid-import': 3,
            'post-import-failed': 4,
            'complete': 4,
        }
        context['state'] = context['object'].state
        context['stepper_number'] = stepper_states[context['object'].state]

        # Add extra state mode for when user has just completed import
        # Won't show when the user navigates to the page from the import batch history listing
        if context['object'].completed and not self.request.GET.get('show_workflow_after_completion'):
            context['hide_stepper'] = True

        # Additional prep
        if context['state'] == 'pre-validate':
            with context['object'].import_sheet.file.open() as import_sheet_raw:
                try:
                    context['preview_data'] = tablib.Dataset().load(import_sheet_raw.read().decode("utf-8-sig"), "csv")
                except Exception as e:
                    error_dataset = tablib.Dataset()
                    error_dataset.headers = (f'Error cannot read CSV file "{os.path.basename(import_sheet_raw.name)}":'
                                             f' {e.__repr__()}',)
                    context['preview_data'] = error_dataset

        if context['object'].completed:
            context['duration'] = context['object'].completed - context['object'].started

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


class ExporterLandingView(HostAdminSyncListView):
    model = ExportBatch
    paginate_by = 25
    queryset = ExportBatch.objects.all().order_by('-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Exporter'
        return context


class ExportBatchCreateView(HostAdminSyncCreateView):
    model = ExportBatch
    fields = ['models_to_export']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Export batch setup'
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)

        form.fields['models_to_export'] = MultipleChoiceField(
            choices=zip(MODEL_ALLOW_LIST, MODEL_ALLOW_LIST)
        )
        return form

    def post(self, request, *args, **kwargs):
        result = super().post(request, *args, **kwargs)
        self.object.started = timezone.now()
        self.object.save()
        try_celery_task_or_fallback_to_synchronous_call(
            background_run_export_batch,
            run_export_batch,
            self.object,
            self.request
        )
        return redirect(reverse('importer_narwhal:exporter-batch', kwargs={'pk': self.object.pk}))


class ExportBatchDetailView(HostAdminSyncDetailView):
    model = ExportBatch

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Export batch: {context['object'].pk}"
        return context


class DownloadExportFileView(HostAdminSyncView):
    """ View that allows users to download an import file.

    """
    def get(self, request, path):
        """ Retrieve the requested import file.

        :param request: Http request object.
        :param path: Full path for the import file.
        :return: Import file to download or link to download file.
        """
        if not path:
            raise Exception('No import file path was specified')
        else:
            # value that will be in import file's file field
            file_field_value = '{b}{p}'.format(b='data-exports/', p=path)
            # import file filtered for whether it exists
            unfiltered_queryset = ExportBatch.objects.all()
            # import file does not exist
            if file_field_value and not unfiltered_queryset.filter(export_file=file_field_value).exists():
                raise Exception('User does not have access to import file')
            # if hosted in Microsoft Azure, storing import files in an Azure Storage account is required
            if AbstractConfiguration.is_using_azure_configuration():
                return self.serve_azure_storage_static_file(name=file_field_value)
            # otherwise use default mechanism to serve files
            else:
                return self.serve_static_file(
                    request=request,
                    path=path,
                    absolute_base_url=settings.MEDIA_URL,
                    relative_base_url='data-exports/',
                    document_root=settings.MEDIA_ROOT
                )
