from django.apps import apps
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied
from reversion.admin import VersionAdmin
from fdp.settings import SITE_HEADER
from inheritable.models import Metable
from .models import Archivable, Confidentiable


class FdpInheritableBaseAdmin:
    """ Hard-codes permissions in admin interfaces.

    See: https://docs.djangoproject.com/en/2.0/topics/auth/default/#permissions-and-authorization

    """

    @classmethod
    def __has_admin_access(cls, request):
        """ Checks whether a user has access to the FDP administrative interface.

        :param request: HTTP request object.
        :return: True if user has access, false otherwise.
        """
        # and has a user AND IS (superuser OR administrator) AND IS active
        return hasattr(request, 'user') and request.user is not None and request.user.has_admin_access

    @classmethod
    def __only_user_alter_matching_user(cls, request, obj):
        """ Enforces that users can only change or delete other users matching their access level.

        :param request: HTTP request object.
        :param obj: Object to change or delete.
        :return: True if object is changeable or deleteable, false otherwise.
        """
        return request.user.only_user_alter_matching_user(obj=obj)

    @classmethod
    def __has_confidential_perm(cls, request, obj):
        """ Checks whether a user has permissions to access for a confidentiable record.

        :param request: Http request object.
        :param obj: Instance of potentially confidentiable model.
        :return: True if user has permissions to access, false otherwise.
        """
        user = request.user
        if obj is None:
            return True
        obj_model = type(obj)
        # Check if direct confidentiality filtering removes instance from user's queryset
        instance_is_accessible = obj_model.objects.get_queryset_for_user(user=user).filter(pk=obj.pk).exists() \
            if isinstance(obj, Confidentiable) else True
        # Check if indirect confidentiality filtering removes instance from user's queryset
        if instance_is_accessible:
            # indirect confidentiality filtering applies to instance
            if isinstance(obj_model, Archivable):
                return obj_model.filter_for_admin(queryset=obj_model.active_objects.all(), user=request.user).filter(
                    pk=obj.pk
                ).exists()
            # indirect confidentiality filtering did not apply to instance
            return True
        # instance was not accessible through direct confidentiality filtering
        else:
            return False

    @staticmethod
    def __has_filter_for_admin_queryset_permission(has_permission, request, obj):
        """ Checks whether user has permissions to change or delete object after its containing queryset has been
        filtered for indirect confidentiality.

        :param has_permission: True if user has permissions to change or delete object after initial check.
        :param request: Http request object.
        :param obj: Object to change or delete.
        :return: True if user has permissions, false otherwise.
        """
        # if has change/delete permission from initial check, and the object to change/delete is defined
        # then check if indirect confidentiality filtering applies
        if has_permission and obj is not None:
            # indirect confidentiality filtering only defined for archivable models
            if isinstance(obj, Archivable):
                obj_model = type(obj)
                changeable_queryset = obj_model.filter_for_admin(queryset=obj_model.objects.all(), user=request.user)
                return has_permission and changeable_queryset.filter(pk=obj.pk).exists()
        return has_permission

    def has_add_permission(self, request):
        """ Checks whether a user has access to add data in the FDP administrative interface.

        :param request: HTTP request object.
        :return: True if user has access to add data, false otherwise.
        """
        return self.__has_admin_access(request=request)

    def has_change_permission(self, request, obj=None):
        """ Checks whether a user has access to change data in the FDP administrative interface.

        :param request: HTTP request object.
        :param obj: Object that is to be edited.
        :return: True if user has access to change data, false otherwise.
        """
        # check if user has admin access, if can alter matching user (if relevant), has confidential permission
        has_change_permission = self.__has_admin_access(
            request=request
        ) and self.__only_user_alter_matching_user(
            request=request, obj=obj
        ) and self.__has_confidential_perm(
            request=request, obj=obj
        )
        return self.__has_filter_for_admin_queryset_permission(
            has_permission=has_change_permission,
            request=request,
            obj=obj
        )

    def has_delete_permission(self, request, obj=None):
        """ Checks whether a user has access to delete data in the FDP administrative interface.

        :param request: HTTP request object.
        :param obj: Object that is to be deleted.
        :return: True if user has access to delete data, false otherwise.
        """
        has_delete_permission = self.__has_admin_access(
            request=request
        ) and self.__only_user_alter_matching_user(
            request=request, obj=obj
        ) and self.__has_confidential_perm(
            request=request, obj=obj
        )
        return self.__has_filter_for_admin_queryset_permission(
            has_permission=has_delete_permission,
            request=request,
            obj=obj
        )

    def has_view_permission(self, request, obj=None):
        """ Checks whether a user has access to view data in the FDP administrative interface.

        :param request: Http request object.
        :param obj: Object that is to be viewed.
        :return: True if user has access to view data, false otherwise.
        """
        has_view_permission = self.__has_admin_access(
            request=request
        ) and self.__only_user_alter_matching_user(
            request=request, obj=obj
        ) and self.__has_confidential_perm(
            request=request, obj=obj
        )
        return self.__has_filter_for_admin_queryset_permission(
            has_permission=has_view_permission,
            request=request,
            obj=obj
        )

    def has_module_permission(self, request):
        """ Checks whether a user has access to a module on the FDP administrative interface's index page and
        has access to a module’s index page.

        :param request: HTTP request object.
        :return: True if user has acces to module, false otherwise.
        """
        return self.__has_admin_access(request=request)


class HostOnlyBaseAdmin:
    """ Hard-codes host administrator only permissions in admin interfaces.

    See: https://docs.djangoproject.com/en/2.0/topics/auth/default/#permissions-and-authorization

    """
    @staticmethod
    def __only_host_admin(request):
        """ Limits access to only host administrators and super users.

        :return: True if user is host administrator or super user, false otherwise.
        """
        return (request.user.is_host and request.user.has_admin_access) or request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        """ Restricts view permissions to only host administrators and super users.

        :param request: Http request object.
        :param obj: Optional object being viewed.
        :return: True if user is host administrator or super user, false otherwise.
        """
        return self.__only_host_admin(request=request)

    def has_add_permission(self, request):
        """ Restricts add permissions to only host administrators and super users.

        :param request: HTTP request object.
        :return: True if user has access to add data, false otherwise.
        """
        return self.__only_host_admin(request=request)

    def has_change_permission(self, request, obj=None):
        """ Restricts change permissions to only host administrators and super users.

        :param request: HTTP request object.
        :param obj: Object that is to be edited.
        :return: True if user has access to change data, false otherwise.
        """
        return self.__only_host_admin(request=request)

    def has_delete_permission(self, request, obj=None):
        """ Restricts delete permissions to only host administrators and super users.

        :param request: HTTP request object.
        :param obj: Object that is to be deleted.
        :return: True if user has access to delete data, false otherwise.
        """
        return self.__only_host_admin(request=request)

    def has_module_permission(self, request):
        """ Restricts module permissions to only host administrators and super users.

        :param request: HTTP request object.
        :return: True if user has access to module, false otherwise.
        """
        return self.__only_host_admin(request=request)


class FdpInheritableAdmin(FdpInheritableBaseAdmin, VersionAdmin):
    """ Allows for admin interfaces to be versioned, and to have hard-coded permissions.

    """
    @staticmethod
    def __get_filtered_queryset(model, queryset, request):
        """ Retrieves a queryset filtered for the user.

        :param model: Model for queryset.
        :param queryset: Queryset to filter for user.
        :param request: Http request object containing user object.
        :return: Queryset filtered for the user.
        """
        u = {'user': request.user}
        return model.objects.get_queryset_for_user(**u) if not queryset \
            else queryset.filter_for_confidential_by_user(**u)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """ Filter foreign keys for user if they are confidentiable.

        :param db_field: Foreign key field.
        :param request: Http request object.
        :param kwargs: Keyword arguments including a queryset that can be filtered.
        :return: Form field for foreign key.
        """
        fk_model = Metable.get_fk_model(foreign_key=db_field)
        k = 'queryset'
        # filter for direct confidentiality
        if issubclass(fk_model, Confidentiable):
            kwargs[k] = self.__get_filtered_queryset(model=fk_model, queryset=kwargs.get(k, None), request=request)
        # filter for indirect confidentiality
        if issubclass(fk_model, Archivable):
            queryset = kwargs.get(k, fk_model.active_objects.all())
            kwargs[k] = fk_model.filter_for_admin(queryset=queryset, user=request.user)
        return super(FdpInheritableAdmin, self).formfield_for_foreignkey(db_field=db_field, request=request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """ Filter many-to-many keys for user if they are confidentiable.

        :param db_field: Many-to-many field.
        :param request: Http request object.
        :param kwargs: Keyword arguements including a queryset that can be filtered.
        :return: Form field for many-to-many key.
        """
        m2m_model = db_field.remote_field.model
        k = 'queryset'
        # filter for direct confidentiality
        if m2m_model and issubclass(m2m_model, Confidentiable):
            kwargs[k] = self.__get_filtered_queryset(model=m2m_model, queryset=kwargs.get(k, None), request=request)
        # filter for indirect confidentiality
        if m2m_model and issubclass(m2m_model, Archivable):
            queryset = kwargs.get(k, m2m_model.active_objects.all())
            kwargs[k] = m2m_model.filter_for_admin(queryset=queryset, user=request.user)
        return super(FdpInheritableAdmin, self).formfield_for_manytomany(db_field=db_field, request=request, **kwargs)

    def get_queryset(self, request):
        """ Filter queryset for user and confidentiality.

        :param request: Http request object.
        :return: Queryset.
        """
        user = request.user
        user_dict = {'user': request.user}
        queryset = super(FdpInheritableAdmin, self).get_queryset(request=request)
        if issubclass(queryset.model, Confidentiable):
            queryset = queryset.filter_for_confidential_by_user(**user_dict)
        if issubclass(queryset.model, Archivable):
            queryset = queryset.model.filter_for_admin(queryset=queryset, user=user)
        return queryset

    def get_search_results(self, request, queryset, search_term):
        """ The get_search_results method modifies the list of objects displayed into those that match the provided
        search term. It accepts the request, a queryset that applies the current filters, and the user-provided search
        term. It returns a tuple containing a queryset modified to implement the search, and a boolean indicating if
        the results may contain duplicates.

        The default implementation searches the fields named in ModelAdmin.search_fields.

        This method may be overridden with your own custom search method. For example, you might wish to search by an
        integer field, or use an external tool such as Solr or Haystack. You must establish if the queryset changes
        implemented by your search method may introduce duplicates into the results, and return True in the second
        element of the return value.

        :param request: Http request object.
        :param queryset:
        :param search_term:
        :return:
        """
        queryset, use_distinct = super(FdpInheritableAdmin, self).get_search_results(
            request=request,
            queryset=queryset,
            search_term=search_term
        )
        if issubclass(queryset.model, Archivable):
            queryset = queryset.model.filter_for_admin(queryset=queryset, user=request.user)
        return queryset, use_distinct

    def history_view(self, request, object_id, extra_context=None):
        """ Renders the history view.

        Ensures only host administrators and superusers can access.

        :param request: Http request object.
        :param object_id: Id of object for which to render history view.
        :param extra_context: Additional context.
        :return: Rendered history view.
        """
        user = request.user
        if user.is_host or user.is_superuser:
            return super(FdpInheritableAdmin, self).history_view(
                request=request,
                object_id=object_id,
                extra_context=extra_context
            )
        else:
            raise PermissionDenied

    def recoverlist_view(self, request, extra_context=None):
        """ Displays a deleted model to allow recovery

        Ensures only host administrators and superusers can access.

        :param request: Http request object.
        :param extra_context: Additional context.
        :return: Rendered recovery view.
        """
        user = request.user
        if user.is_host or user.is_superuser:
            return super(FdpInheritableAdmin, self).recoverlist_view(request=request, extra_context=extra_context)
        else:
            raise PermissionDenied


class ArchivableAdmin(admin.ModelAdmin):
    """ Allows for admin interfaces to be filtered by whether a record is archived or not.

    """
    list_display = []
    list_filter = []

    def get_readonly_fields(self, request, obj=None):
        """ The get_readonly_fields method is given the HttpRequest and the obj being edited (or None on an add form)
        and is expected to return a list or tuple of field names that will be displayed as read-only, as described
        above in the ModelAdmin.readonly_fields section.

        :param request: Http request object.
        :param obj: Object being edited, or None if being created.
        :return: List or tuple of read only field names.
        """
        readonly_fields = super(ArchivableAdmin, self).get_readonly_fields(request=request, obj=obj)
        is_archived_field = 'is_archived'
        # make is_archived into a read-only field
        if is_archived_field not in readonly_fields:
            return [*readonly_fields, is_archived_field]
        # is_archived is already a read-only field
        else:
            return readonly_fields


class ConfidentiableAdmin(ArchivableAdmin):
    """ Allows for admin interfaces to be filtered by access levels (e.g. specific FDP organizations and user role).

    """
    list_display = ArchivableAdmin.list_display + ['for_admin_only', 'all_fdp_organizations']
    list_filter = ArchivableAdmin.list_filter + ['for_admin_only', 'for_host_only', 'fdp_organizations']

    def get_queryset(self, request):
        """ Filters queryset so that records displayed are confidentiality appropriate for user.

        :param request: Http request object.
        :return: Confidentiality filtered queryset.
        """
        queryset = super(ConfidentiableAdmin, self).get_queryset(request=request)
        return queryset.filter_for_confidential_by_user(user=request.user)

    def get_readonly_fields(self, request, obj=None):
        """ The get_readonly_fields method is given the HttpRequest and the obj being edited (or None on an add form)
        and is expected to return a list or tuple of field names that will be displayed as read-only, as described
        above in the ModelAdmin.readonly_fields section.

        :param request: Http request object.
        :param obj: Object being edited, or None if being created.
        :return: List or tuple of read only field names.
        """
        readonly_fields = super(ConfidentiableAdmin, self).get_readonly_fields(request=request, obj=obj)
        # user is not a host user or super user, so make host only field read-only
        if not (request.user.is_host or request.user.is_superuser):
            return [*readonly_fields, 'for_host_only']
        # otherwise, no changes
        else:
            return readonly_fields


class HostOnlyAdmin(HostOnlyBaseAdmin, FdpInheritableAdmin):
    """ Restricts admin interfaces to only host administrators and super users.

    """
    pass


#  Change "Django Administration" site title
admin.site.site_header = _(SITE_HEADER)


#  Override the verbose name for Django-Axes
apps.get_app_config('axes').verbose_name = _('Login')
