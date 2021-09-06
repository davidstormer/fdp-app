from django.utils.translation import gettext as _
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from inheritable.models import AbstractUrlValidator, AbstractConfiguration
from inheritable.views import HostAdminSyncTemplateView, HostAdminSyncFormView, HostAdminSyncCreateView, \
    HostAdminSyncListView, HostAdminSyncView
from .forms import WholesaleTemplateForm, WholesaleStartImportForm
from .models import WholesaleImport, WholesaleImportRecord, ModelHelper
from csv import writer as csv_writer


class IndexTemplateView(HostAdminSyncTemplateView):
    """ Page that allows users to select their desired usage of the wholesale import tool, such as to add or update
    data.

    """
    template_name = 'wholesale_home.html'

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(IndexTemplateView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Wholesale'),
            'description': _('Select desired usage of the wholesale import tool.'),
        })
        return context


class TemplateFormView(HostAdminSyncFormView):
    """ Page that allows users to select the combination from the data model for which to generate a wholesale import
    template.

    """
    template_name = 'wholesale_template.html'
    form_class = WholesaleTemplateForm
    #: ignored, since HTTP response will contain bytes representing file for template that was generated
    success_url = reverse_lazy('wholesale:template')

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(TemplateFormView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Template'),
            'description': _('Generate templates for specific combinations of the data model.'),
            'external_id_suffix': WholesaleImport.external_id_suffix,
            'true_bools': ','.join([f'"{t}"' for t in WholesaleImport.true_booleans]),
            'false_bools': ','.join([f'"{f}"' for f in WholesaleImport.false_booleans]),
            'date_format': WholesaleImport.date_format,
            'datetime_format': WholesaleImport.datetime_format,
            'delimiter': WholesaleImport.csv_delimiter,
            'quotechar': WholesaleImport.csv_quotechar,
        })
        return context

    def form_valid(self, form):
        """ Generates template for specific combination of data model that was submitted through the form by the user.

        :param form: Form defining the specific combination of data model.
        :return: Http response object containing the bytes for the generated template CSV file.
        """
        super().form_valid(form=form)
        template_headings = form.get_wholesale_template_headings()
        file_name = 'wholesale'
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{file_name}.csv"'
        writer = csv_writer(response)
        writer.writerow(template_headings)
        return response


class StartImportCreateView(HostAdminSyncCreateView):
    """ Page that allows users to start an import of data through a wholesale import template.

    """
    template_name = 'wholesale_start_import.html'
    form_class = WholesaleStartImportForm

    def __init__(self, *args, **kwargs):
        """ Initialize primary key and corresponding object used as a reference for wholesale import in database.

        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'object'):
            self.object = None
        self.wholesale_import_pk = None

    def get_success_url(self):
        """ Retrieves the URL to which the user should be redirected after the import or a desired step before it, is
        performed.

        :return: URL to which user should be redirected.
        """
        # wholesale import is recorded in the database, but may or may not be done
        if self.wholesale_import_pk:
            #: TODO: If user selects basic validation before importing data.
            #: TODO: if self.object.before_import == WholesaleImport.validate_value:
            #: TODO:     reverse('wholesale:confirm_import', kwargs={'pk'
            return reverse('wholesale:log', kwargs={'pk': self.wholesale_import_pk})
        # wholesale import was not recorded in the database
        else:
            return reverse('wholesale:logs')

    def get_initial(self):
        """ Sets defaults for the form representing the wholesale import to start.

        :return: Dictionary containing initial data for form.
        """
        initial = super().get_initial()
        initial['before_import'] = WholesaleImport.nothing_value
        initial['on_error'] = WholesaleImport.stop_value
        return initial

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(StartImportCreateView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Start import'),
            'description': _('Start an import of data through wholesale import template.'),
        })
        return context

    def form_valid(self, form):
        """ Add additional data to the wholesale import record before saving, import data and update the record.

        :param form: Form defining wholesale import record.
        :return: Http response to redirect user after wholesale import record is added.
        """
        self.object = form.save(commit=False)
        self.object.user = self.request.user.email
        self.object.full_clean()
        self.object.save()
        # import the data
        wholesale_import = self.object.do_import()
        self.wholesale_import_pk = wholesale_import.pk
        return HttpResponseRedirect(self.get_success_url())


class ImportLogListView(HostAdminSyncListView):
    """ Page that allows users to review the log for a specific wholesale import.

    """
    template_name = 'wholesale_import_log.html'
    model = WholesaleImportRecord

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(ImportLogListView, self).get_context_data(**kwargs)
        pk = self.kwargs['pk']
        context.update({
            'title': _(f'#{pk}'),
            'description': _(f'Review a log for wholesale import #{pk}.'),
            'wholesale_import': WholesaleImport.objects.get(pk=pk),
        })
        return context

    def get_queryset(self):
        """ Adds a link through the Advanced Admin for each wholesale import record to its corresponding database
        record.

        :return: Queryset used to populate ListView.
        """
        queryset = super().get_queryset()
        queryset = queryset.filter(wholesale_import_id=self.kwargs['pk'])
        # cache used to map models to their corresponding app, e.g. {... 'person':'core', ...}
        cache_dict = {}
        # cycle through all wholesale import records and add a link through the Advanced Admin to the corresponding
        # database record
        for instance in queryset:
            # database record may exist
            if instance.instance_pk:
                model = instance.model_name
                if model not in cache_dict:
                    app = (ModelHelper.get_app_name(model=model)).lower()
                    cache_dict[model] = app
                else:
                    app = cache_dict[model]
                instance.admin_url = reverse(f'admin:{app}_{model.lower()}_change', args=[instance.instance_pk])
            # database record does not exist
            else:
                instance.admin_url = None
        return queryset


class ImportLogsListView(HostAdminSyncListView):
    """ Page that allows users to review the wholesale import logs and to navigate to any of them.

    """
    template_name = 'wholesale_import_logs.html'
    model = WholesaleImport

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(ImportLogsListView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Logs'),
            'description': _('Review wholesale import logs.'),
        })
        return context


class DownloadWholesaleImportFileView(HostAdminSyncView):
    """ View that allows users to download a wholesale import file.

    """
    def get(self, request, path):
        """ Retrieve the requested wholesale import file.

        :param request: Http request object.
        :param path: Full path for the wholesale import file.
        :return: Wholesale import file to download or link to download file.
        """
        if not path:
            raise Exception(_('No wholesale import file path was specified'))
        else:
            # value that will be in wholesale import file field
            file_field_value = '{b}{p}'.format(b=AbstractUrlValidator.WHOLESALE_BASE_URL, p=path)
            # wholesale import file filtered for whether it exists
            unfiltered_queryset = WholesaleImport.objects.all()
            # wholesale import file does not exist
            if file_field_value and not unfiltered_queryset.filter(file=file_field_value).exists():
                raise Exception(_('User does not have access to wholesale import file'))
            # if hosted in Microsoft Azure, storing wholesale import files in an Azure Storage account is required
            if AbstractConfiguration.is_using_azure_configuration():
                return self.serve_azure_storage_static_file(name=file_field_value)
            # otherwise use default mechanism to serve files
            else:
                return self.serve_static_file(
                    request=request,
                    path=path,
                    absolute_base_url=settings.MEDIA_URL,
                    relative_base_url=AbstractUrlValidator.WHOLESALE_BASE_URL,
                    document_root=settings.MEDIA_ROOT
                )
