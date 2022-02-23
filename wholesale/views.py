from django.utils.translation import gettext as _
from django.shortcuts import redirect
from django.utils.html import mark_safe
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from inheritable.models import AbstractUrlValidator, AbstractConfiguration
from inheritable.views import HostAdminSyncTemplateView, HostAdminSyncFormView, HostAdminSyncCreateView, \
    HostAdminSyncListView, HostAdminSyncView
from .forms import WholesaleTemplateForm, WholesaleCreateImportForm, WholesaleStartImportForm
from .models import WholesaleImport, WholesaleImportRecord, ModelHelper
from csv import writer as csv_writer
from json import dumps as json_dumps


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
            'title': _('Importer'),
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
            'model_relations': mark_safe(json_dumps(WholesaleTemplateForm.get_model_relations())),
            'auto_external_id': WholesaleImport.get_auto_external_id(
                uuid='<UUID>',
                group='<GROUP>',
                row_num='<ROW_NUM>'
            )
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


class CreateImportCreateView(HostAdminSyncCreateView):
    """ Page that allows users to create a batch of data that can be imported through a wholesale import template.

    """
    template_name = 'wholesale_create_import.html'
    form_class = WholesaleCreateImportForm

    def __init__(self, *args, **kwargs):
        """" Initialize primary key and corresponding object used as a reference for wholesale import record in
        database.
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'object'):
            self.object = None
        self.wholesale_import_pk = None

    def get_success_url(self):
        """ Retrieves the URL to which the user should be redirected after the import.

        :return: URL to which user should be redirected.
        """
        # wholesale import has been created in the database, and so is ready to be started
        if self.wholesale_import_pk:
            return reverse('wholesale:start_import', kwargs={'pk': self.wholesale_import_pk})
        # wholesale import was not created in the database
        else:
            return reverse('wholesale:logs')

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(CreateImportCreateView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Create import'),
            'description': _('Create a batch of data to import through the wholesale import template.'),
        })
        return context

    def form_valid(self, form):
        """ Add additional data to the wholesale import record before creating it in the database.

        :param form: Form defining wholesale import record.
        :return: Http response to redirect user after wholesale import record is created.
        """
        self.object = form.save(commit=False)
        self.object.user = self.request.user.email
        self.object.uuid = WholesaleImport.get_uuid()
        self.object.full_clean()
        self.object.save()
        self.wholesale_import_pk = self.object.pk
        return HttpResponseRedirect(self.get_success_url())


class StartImportFormView(HostAdminSyncFormView):
    """ Page that allows users to start an import for a batch of data in a wholesale import template.

    """
    template_name = 'wholesale_start_import.html'
    form_class = WholesaleStartImportForm

    def __init__(self, *args, **kwargs):
        """" Initialize the attributes that will summarize the import for the user, as well as the placeholder for the
        requested wholesale import model instance.
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        # action of import such as "add", "update", etc.
        self.__action_txt = None
        # list of tuples representing models and their corresponding fields
        self.__models_with_fields = None
        # number of data rows in CSV template
        self.__num_of_data_rows = None
        # model instance corresponding to requested wholesale import record, will be set in dispatch(...)
        self.__wholesale_import = None

    def get_success_url(self):
        """ Retrieves the URL to which the user should be redirected after the import.

        :return: URL to which user should be redirected.
        """
        return reverse('wholesale:log', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(StartImportFormView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Start Import'),
            'description': _('Start importing data in wholesale import template.'),
            'action_txt': self.__action_txt,
            'models_with_fields': self.__models_with_fields,
            'num_of_data_rows': self.__num_of_data_rows,
            'pk': self.kwargs['pk']
        })
        return context

    def dispatch(self, request, *args, **kwargs):
        """ Ensures that only existing wholesale import records that are ready for import can be access through this
        view.

        :param request: Http request object.
        :param args:
        :param kwargs:
        :return: Http response.
        """
        pk = self.kwargs['pk']
        # import doesn't exist
        if not WholesaleImport.objects.filter(pk=pk).exists():
            raise Exception(f'Import {pk} does not exist and so cannot be started')
        self.__wholesale_import = WholesaleImport.objects.get(pk=pk)
        # data is not ready for import (e.g. maybe already imported)
        if not self.__wholesale_import.is_ready_for_import:
            return redirect(reverse('wholesale:log', kwargs={'pk': pk}))
        return super().dispatch(request=request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """ Only sending a request through the GET method to this view, if the the wholesale import has been created,
        but not yet started.

        :param request: Http request object.
        :param args:
        :param kwargs:
        :return: Http response.
        """
        # convert all implicit references between related models to be explicit references by using automatically
        # generated external IDs
        self.__wholesale_import.convert_implicit_references()
        # during the above conversion, data structures are built and populated with metadata about the template
        # action of import such as "add", "update", etc.
        self.__action_txt = self.__wholesale_import.get_action_display()
        # list of tuples representing models and their corresponding fields
        self.__models_with_fields = self.__wholesale_import.get_models_with_fields()
        # number of data rows in CSV template
        self.__num_of_data_rows = self.__wholesale_import.get_num_of_data_rows()
        return super().get(request=request, *args, **kwargs)

    def form_valid(self, form):
        """ Performs import of the data.

        :param form: Empty form whose submission represents the user's request to start the import.
        :return: Http response redirecting to the relevant page following an import.
        """
        response = super().form_valid(form=form)
        # perform the import
        self.__wholesale_import.do_import()
        return response


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
            'title': _('Batches'),
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
