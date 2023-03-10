from django.shortcuts import redirect
from django.core.exceptions import NON_FIELD_ERRORS
from django.core.files.storage import get_storage_class
from django.http import JsonResponse
from django.views.generic import TemplateView, FormView, RedirectView, ListView, DetailView, View, CreateView, \
    UpdateView
from django.urls import reverse
from django.utils.http import quote_plus
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin, AccessMixin
from two_factor.views.mixins import OTPRequiredMixin
from django.utils.translation import gettext as _
from django.views.static import serve
from django.conf import settings
from fdpuser.models import FdpUser
from fdp.settings import SITE_HEADER
from reversion.views import RevisionMixin
from reversion import set_comment as reversion_set_comment
from .forms import PopupForm
from .models import Archivable, Confidentiable, AbstractUrlValidator, AbstractJson, JsonError, AbstractFileValidator
from json import loads as json_loads


class PostOrGetOnlyMixin(AccessMixin):
    """ Mixin limiting requests to only GET or POST.

    """
    def dispatch(self, request, *args, **kwargs):
        """ Check that the HTTP request method is either GET or POST.

        :param request: HTTP request object.
        :param args:
        :param kwargs:
        :return:
        """
        if request.method not in ['GET', 'POST']:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class CoreAccessMixin(OTPRequiredMixin, LoginRequiredMixin, UserPassesTestMixin, PostOrGetOnlyMixin):
    """ Mixin limiting access for core elements to users who are authorized.

    Log in is required, and users must be able to view core data.

    Only POST or GET request methods accepted.

    """
    def test_func(self):
        """ Used to test the user for UserPassesTestMixin.

        Ensures that user can view core data for the FDP.

        :return: True if user passes the test, false otherwise.
        """
        request = getattr(self, 'request', None)
        user = getattr(request, 'user', None)
        return FdpUser.can_view_core(user=user)


class AdminAccessMixin(CoreAccessMixin):
    """ Mixin limiting access for admin only elements to users who are authorized.

    Log in is required, and users must have admin permissions and core permissions.

    Only POST and GET request methods accepted.

    """
    def test_func(self):
        """ Used to test the user for UserPassesTestMixin.

        Ensures that user can view admin data for the FDP (implicitly users can also view core data).

        :return: True if user passes the test, false otherwise.
        """
        request = getattr(self, 'request', None)
        user = getattr(request, 'user', None)
        return super(AdminAccessMixin, self).test_func() and FdpUser.can_view_admin(user=user)


class ContextDataMixin:
    """ Mixin that allows for adding additional context data such as permissions and theme customization for the site.

    """
    def _add_context(self, context):
        """ Adds context data such as permissions and theme customization for the site.

        :param context: Dictionary containing some context data, into which permissions and theme are added.
        :return: Expanded context data dictionary.
        """
        request = getattr(self, 'request', None)
        user = getattr(request, 'user', None)
        context['is_admin'] = FdpUser.can_view_admin(user=user)
        context['only_external_auth'] = user.only_external_auth
        context['site_header'] = _(SITE_HEADER)
        context['site_title'] = _('FDP System')
        context['has_permission'] = True
        return context


class AsyncContextDataMixin:
    """ Mixin that allows for adding additional context data such as localized labels and JSON parameter names
    for an asynchronously rendered page.

    """
    @staticmethod
    def _add_async_context(context):
        """ Adds context data such as localized labels and JSON parameter names for an asynchronously rendered
        page.

        :param context: Dictionary containing some context data, into which localized labels and JSON parameters
        are added.
        :return: Expanded context data dictionary.
        """
        context['localized_error'] = _('Error')
        context['localized_cnf_tle'] = _('Are you sure?')
        context['localized_err_tle'] = _('There was a problem...')
        context['localized_browser_unsupported'] = _('Your Internet browser is not supported. Please use an updated '
                                                     'version of Mozilla Firefox or Google Chrome.')
        context['localized_popup_error'] = _('This popup window is disconnected from the window where it was created. '
                                             'Please close both windows and try again.')
        context['localized_loading'] = _('Loading')
        context['localized_raw_err_tle'] = _('Something unexpected happened...')
        context['localized_raw_err_dtl'] = _('Error details')
        context['localized_raw_err_msg'] = _('Please open the link below to see the error details.')
        context['localized_save'] = _('Save')
        context['localized_cancel'] = _('Cancel')
        context['localized_click_to_edit'] = _('Click to edit')
        context['json_is_error'] = AbstractUrlValidator.JSON_ERR_PARAM
        context['json_is_empty'] = AbstractUrlValidator.JSON_EMP_PARAM
        context['json_is_data'] = AbstractUrlValidator.JSON_DAT_PARAM
        context['json_is_html'] = AbstractUrlValidator.JSON_HTM_PARAM
        context['json_error'] = AbstractUrlValidator.JSON_ERR_DAT_PARAM
        context['json_data'] = AbstractUrlValidator.JSON_DAT_DAT_PARAM
        context['json_html'] = AbstractUrlValidator.JSON_HTM_DAT_PARAM
        return context


class PopupContextMixin:
    """ Mixing that allows for adding additional / optional context data in scenarios where a view is rendered as a
    popup.

    """
    @staticmethod
    def _add_popup_context(context):
        """ Adds context data such as parameter names for a view rendered as a popup.

        :param context: Dictionary containing some context data, into which parameter names are added.
        :return: Expanded context data dictionary.
        """
        context['localized_browser_unsupported'] = _('Your Internet browser is not supported. Please use an updated '
                                                     'version of Mozilla Firefox or Google Chrome.')
        context['localized_popup_error'] = _('This popup window is disconnected from the window where it was created. '
                                             'Please close both windows and try again.')
        context['popup_key'] = AbstractUrlValidator.GET_POPUP_PARAM
        context['popup_value'] = AbstractUrlValidator.GET_POPUP_VALUE
        context['popup_id_key'] = AbstractUrlValidator.GET_UNIQUE_POPUP_ID_PARAM
        context['popup_field'] = PopupForm.popup_id_field
        return context

    @staticmethod
    def _redirect_to_close_popup(popup_id, pk, str_rep):
        """ Retrieves a redirect to the page that will close a popup, and pass data back to the window opener.

        :param popup_id: Id of popup.
        :param pk: Primary key of object that was added or selected through the popup window.
        :param str_rep: String representation of object that was added or selected through the popup window.
        :return: Link to page that will close the popup.
        """
        return reverse('changing:close_popup', kwargs={'popup_id': popup_id, 'pk': pk, 'str_rep': quote_plus(str_rep)})


class SecuredSyncView(CoreAccessMixin, View):
    """ Secure synchronously base view.

    Log is in required, and users must be able to view core data.

    Only POST or GET request methods accepted.

    """
    @staticmethod
    def serve_static_file(request, path, absolute_base_url, relative_base_url, document_root):
        """ Default mechanism to serve a static file, e.g. attachment or person photo, requested by the user.

        :param request: Http request object through which file was selected.
        :param path: Full path of static file.
        :param absolute_base_url: Absolute base portion that may be included in the static file path that should be
        removed, e.g. MEDIA_URL.
        :param relative_base_url: Context-driven base portion of static file path that must be included,
        e.g. AbstractUrlValidator.ATTACHMENT_BASE_URL.
        :param document_root: Root that is prepended to the full path of static file, e.g. MEDIA_ROOT.
        :return: Static file that is served.
        """
        # remove the absolute base url (e.g. media url) if appended to the path
        b = absolute_base_url
        if path.startswith(b):
            path = path[len(b):]
        # add in the relative base url (e.g. source base) if not yet prepended
        b = relative_base_url
        if not path.startswith(b):
            path = '{b}{p}'.format(b=b, p=path)
        # verify that only static files from the media root folder are served
        # will raise exception if root folder is unexpected
        AbstractFileValidator.check_path_is_expected(
            relative_path=path,
            root_path=document_root,
            expected_path_prefix=settings.MEDIA_ROOT,
            err_msg=_('Path is not valid'),
            err_cls=Exception
        )
        return serve(request, path, document_root=document_root, show_indexes=False)

    @staticmethod
    def serve_azure_storage_static_file(name):
        """ Mechanism for Azure Storage account to serve a static file, e.g. attachment or person photo, requested by
        the user.

        :param name: Relative path of file including file name and extension.
        :return: Redirect to an expiring SAS URL for the file.
        """
        # class for storage backend used to manage user-uploaded media files
        media_azure_storage_cls = get_storage_class(settings.DEFAULT_FILE_STORAGE)
        # instance for storage backend used to manage user-uploaded media files
        media_azure_storage = media_azure_storage_cls()
        # expiring URL with SAS
        sas_expiring_url = media_azure_storage.get_sas_expiring_url(name)
        # redirect
        return redirect(sas_expiring_url)


class SecuredSyncRedirectView(CoreAccessMixin, RedirectView):
    """ Secure synchronously redirected view.

    Log is in required, and users must be able to view core data.

    Only POST or GET request methods accepted.

    """
    permanent = False
    query_string = False


class SecuredSyncTemplateView(CoreAccessMixin, ContextDataMixin, TemplateView):
    """ Secure synchronously rendered view rendering a template.

    Log is in required, and users must be able to view core data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_context(context)


class AdminSyncTemplateView(AdminAccessMixin, ContextDataMixin, TemplateView):
    """ Admin only synchronously rendered view rendering a template.

    Log is in required, and users must be able to view admin only data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_context(context)


class AdminAsyncTemplateView(AdminSyncTemplateView, AsyncContextDataMixin):
    """ Admin only synchronously rendered view rendering a template that also supports asynchronous requests.

    Log is in required, and users must be able to view admin only data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as parameter names and localized messages for asynchronous requests.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_async_context(context)


class SecuredSyncFormView(CoreAccessMixin, ContextDataMixin, FormView):
    """ Secure synchronously rendered view rendering a form.

    Log is in required, and users must be able to view core data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_context(context)


class AdminSyncFormView(AdminAccessMixin, ContextDataMixin, FormView):
    """ Admin only synchronously rendered view rendering a form.

    Log is in required, and users must be able to view admin only data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_context(context)


class SecuredSyncListView(CoreAccessMixin, ContextDataMixin, ListView):
    """ Secure synchronously rendered view rendering a filtered and paginated list of objects.

    Log is in required, and users must be able to view core data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_context(context)


class SecuredSyncDetailView(CoreAccessMixin, ContextDataMixin, DetailView):
    """ Secure synchronously rendered view rendering a template.

    Log is in required, and users must be able to view core data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_context(context)


class AdminSyncCreateView(AdminAccessMixin, ContextDataMixin, RevisionMixin, CreateView):
    """ Admin only synchronously rendered view to create an object.

    Log is in required, and users must be able to view admin only data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        context.update({'is_editing': False})
        return self._add_context(context)

    def form_valid(self, form):
        """ Identify the action being taken to create a Django-Reversion record.

        :param form: Form containing model instance to create.
        :return: Response once model instance is saved.
        """
        reversion_set_comment(_('Created through data management wizard'))
        return super(AdminSyncCreateView, self).form_valid(form=form)


class AdminAsyncCreateView(AdminSyncCreateView, AsyncContextDataMixin):
    """ Admin only synchronously rendered view to create an object, and also supporting asynchronous requests.

    Log is in required, and users must be able to view admin only data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as parameter names and localized messages for asynchronous requests.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_async_context(context)


class AdminSyncUpdateView(AdminAccessMixin, ContextDataMixin, RevisionMixin, UpdateView):
    """ Admin only synchronously rendered view to update an object.

    Log is in required, and users must be able to view admin only data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as permissions and theme customization.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        context.update({'is_editing': True})
        return self._add_context(context)

    def get_object(self, queryset=None):
        """ Ensure that user has sufficient permissions to update object.

        For example, if object inherits from the Confidentiable class, then filter by the user's permissions.

        :param queryset: Queryset from which to retrieve object.
        :return: Object to update. If user does not have sufficient permissions, then a PermissionError is raised.
        """
        obj = super(AdminSyncUpdateView, self).get_object(queryset=queryset)
        cls = self.model
        user = self.request.user
        # if the model has inherited from the Confidentiable abstract class
        # then ensure the user has sufficient permissions
        if issubclass(cls, Confidentiable):
            # queryset containing all objects that are accessible to the user
            accessible_qs = cls._default_manager.all().filter_for_confidential_by_user(user=user)
            # object user is attempting to update is not in the queryset containing all accessible objects
            if not accessible_qs.filter(pk=obj.pk).exists():
                raise PermissionError(_('User does not have permission to update this object'))
        # if the model is linked to a model that inherited from the Confidentiable abstract class
        # then ensure the user has sufficient permissions
        if issubclass(cls, Archivable):
            # queryset containing all objects that are accessible to the user
            accessible_qs = cls.filter_for_admin(queryset=cls._default_manager.all(), user=user)
            # object user is attempting to update is not in the queryset containing all accessible objects
            if not accessible_qs.filter(pk=obj.pk).exists():
                raise PermissionError(_('User does not have permission to update this object'))
        return obj

    def form_valid(self, form):
        """ Identify the action being taken to update a Django-Reversion record.

        :param form: Form containing model instance to update.
        :return: Response once model instance is saved.
        """
        reversion_set_comment(_('Updated through data management wizard'))
        return super(AdminSyncUpdateView, self).form_valid(form=form)


class AdminAsyncUpdateView(AdminSyncUpdateView, AsyncContextDataMixin):
    """ Admin only synchronously rendered view to update an object, and also supporting asynchronous requests.

    Log is in required, and users must be able to view admin only data.

    Only POST or GET request methods accepted.

    """
    def get_context_data(self, **kwargs):
        """ Adds additional context such as parameter names and localized messages for asynchronous requests.

        :param kwargs:
        :return: Expanded context data dictionary.
        """
        context = super().get_context_data(**kwargs)
        return self._add_async_context(context)


class AdminAsyncJsonView(AdminAccessMixin, View):
    """  Admin only view accepting asynchronous requests from which all views accepting asynchronous requests inherit.

    Log is in required, and users must be ale to view admin only data.

    Only POST request methods accepted.

    See: https://docs.djangoproject.com/en/2.1/topics/class-based-views/mixins/#more-than-just-html

    """
    http_method_names = ['post']

    @staticmethod
    def get_post_data(request):
        """ Retrieves the data that was sent via the POST method during an asynchronous request.

        :param request: Http request object containing the data sent via the POST method.
        :return: Dictionary of data submitted via POST.
        """
        post_data = json_loads(request.body.decode(AbstractUrlValidator.ENCODING))
        return post_data

    @staticmethod
    def render_to_response(json, **response_kwargs):
        """ Render the JSON formatted data as a response.

        :param json: An instantiated object that inherits from bedrock.models.AbstractJson and represents the JSON to
        send back to the client.
        :param response_kwargs: Keyword arguments passed to JsonResponse.
        :return: JSON formatted response.
        """
        if not issubclass(type(json), AbstractJson):
            raise Exception(_('JSON response must be a subclass of AbstractJson'))
        return JsonResponse(json.get_json_dict(), **response_kwargs)

    def get(self, request, *args, **kwargs):
        """ Block all GET method interactions.

        :param request: Http request object.
        :param args: Ignored.
        :param kwargs: Ignored.
        :return: Nothing.
        """
        raise Exception(_('Use POST method to interact with this view.'))

    @staticmethod
    def jsonify_validation_error(err, b):
        """ Creates a JSON object storing the dictionary of validation errors.

        :param err: Dictionary of validation errors raised during model validation.
        :param b: Localized text that precedes the validation errors. For example, "Data could not be added.".
        :return: JSON object storing all validation errors.
        """
        sep = '. '
        keys = list(err.message_dict.keys())
        str_err = sep.join(
            [sep.join(err.message_dict[k]) if k == NON_FIELD_ERRORS
             else '{a}{b}'.format(
                a=_('Field \'{f}\' issue: '.format(f=k)), b=sep.join(err.message_dict[k])
            ) for k in keys]
        )
        json = JsonError(error='{b} {e}{d}'.format(b=b, e=str_err, d='' if str_err.endswith('.') else '.'))
        return json

    @staticmethod
    def jsonify_error(err, b):
        """ Creates a JSON object storing an error.

        :param err: General exception to store in JSON object.
        :param b: Localized text that precedes the error. For example, "Data could not be added.".
        :return: JSON object storing error.
        """
        str_err = str(err)
        json = JsonError(error='{b} {e}{d}'.format(b=b, e=str_err, d='' if str_err.endswith('.') else '.'))
        return json
