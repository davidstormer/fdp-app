from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from axes.admin import AccessAttemptAdmin, AccessLogAdmin
from axes.models import AccessAttempt, AccessLog
from cspreports.admin import CSPReportAdmin
from cspreports.models import CSPReport
from .models import FdpUser, FdpOrganization, PasswordReset, FdpCSPReport, Eula
from .forms import FdpUserChangeForm, FdpUserCreationForm
from inheritable.admin import FdpInheritableAdmin, ArchivableAdmin, FdpInheritableBaseAdmin, HostOnlyAdmin, \
    HostOnlyBaseAdmin


@admin.register(FdpOrganization)
class FdpOrganizationAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for organizations to which FDP users can belong.

    """
    _list_display = ['name'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['name'] + ArchivableAdmin.list_filter
    search_fields = ['name']
    ordering = ['name']


@admin.register(FdpUser)
class FdpUserAdmin(FdpInheritableAdmin, UserAdmin):
    """ Admin interface for FDP users.

    """
    form = FdpUserChangeForm
    add_form = FdpUserCreationForm
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {
            'fields': (
                'is_active', 'is_host', 'is_administrator', 'is_superuser', 'fdp_organization', 'only_external_auth'
            )
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'agreed_to_eula')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    _list_display = ['email', 'is_active', 'is_administrator', 'is_host', 'fdp_organization', 'only_external_auth']
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['is_active', 'is_administrator', 'is_host', 'fdp_organization', 'only_external_auth']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    filter_horizontal = []

    def get_form(self, request, obj=None, **kwargs):
        """ Retrieves the change form and adds onto it the HTTP request object, so that the user making the changes can
        be used to stop permission escalation.

        :param request: Http request object with user making changes.
        :param obj: Instance of model upon which form is based. May be None.
        :param kwargs: Additional keyword arguements.
        :return: Change form.
        """
        form = super(FdpUserAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        return form

    def get_queryset(self, request):
        """ Filters the queryset so that guest administrators can only see/access users relevant to them.

        :param request: HTTP request through which queryset is retrieved.
        :return: Filtered queryset.
        """
        qs = super(FdpUserAdmin, self).get_queryset(request=request)
        user = request.user
        # guest administrator
        if not (user.is_superuser or user.is_host):
            qs = qs.filter(is_host=False, is_superuser=False, only_external_auth=False)
            # guest administrator has FDP organization
            if user.fdp_organization:
                qs = qs.filter(fdp_organization_id=user.fdp_organization.pk)
            # guest administrator does not have FDP organization
            else:
                qs = qs.filter(fdp_organization__isnull=True)
        # host administrator
        elif user.is_host and user.is_administrator:
            qs = qs.filter(is_superuser=False)
        return qs

    def get_readonly_fields(self, request, obj=None):
        """ The get_readonly_fields method is given the HttpRequest and the obj being edited (or None on an add form)
        and is expected to return a list or tuple of field names that will be displayed as read-only, as described
        above in the ModelAdmin.readonly_fields section.

        :param request: Http request object.
        :param obj: Object being edited, or None if being created.
        :return: List or tuple of read only field names.
        """
        readonly_fields = super(FdpUserAdmin, self).get_readonly_fields(request=request, obj=obj)
        # these fields are read-only for all users
        readonly_fields_for_all = [*readonly_fields, 'is_superuser', 'agreed_to_eula']
        user = request.user
        # user is a superuser, so read-only fields are: defaults and is_superuser
        if user.is_superuser:
            return readonly_fields_for_all
        # user is not a super, so read-only fields will include only_external_auth
        else:
            readonly_fields_for_not_super_user = [*readonly_fields_for_all, 'only_external_auth']
            # user is not a super user but is a host administrator
            if user.is_host:
                return readonly_fields_for_not_super_user
            # user is not a super user and is not a host administrator (i.e. user is guest administrator), so read-only
            # fields will also include is_host and FDP organization
            else:
                return [*readonly_fields_for_not_super_user, 'is_host', 'fdp_organization']


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    """ Admin interface for password resets for FDP users.

    """
    readonly_fields = ['fdp_user', 'timestamp', 'ip_address']
    _list_display = ['fdp_user', 'ip_address', 'timestamp']
    list_display = _list_display
    list_display_links = _list_display
    ordering = ['fdp_user__email']


#  Unregister admin for failed logins since it is registered below
admin.site.unregister(AccessAttempt)


@admin.register(AccessAttempt)
class FdpAccessAttemptAdmin(HostOnlyAdmin, AccessAttemptAdmin):
    """ Include inheritable permissions for Django Axes model handling failed logins.

    """
    pass


#  Unregister admin for successful logins since it is registered below
admin.site.unregister(AccessLog)


@admin.register(AccessLog)
class FdpAccessLogAdmin(HostOnlyAdmin, AccessLogAdmin):
    """ Include inheritable permissions for Django Axes model handling successful logins.

    """
    pass


#  Django's built-in permissions are unused, so remove them from the admin interface
admin.site.unregister(Group)


#  Unregister admin for Content Security Policy violations since it is registered below
admin.site.unregister(CSPReport)


@admin.register(FdpCSPReport)
class FdpCSPReportAdmin(HostOnlyBaseAdmin, FdpInheritableBaseAdmin, CSPReportAdmin):
    """ Include inheritable permissions for Django Content Security Policy Reports model handling policy violations.

    """
    def has_add_permission(self, request):
        """ Disable ability to add CSP reports through the admin interface.

        :param request: Http request object.
        :return: False always.
        """
        return False


@admin.register(Eula)
class EulaAdmin(HostOnlyAdmin):
    """ Admin interface for user-uploaded end-user licence agreements (EULAs).

    """
    def has_change_permission(self, request, obj=None):
        """ Disable ability to change EULAs through the admin interface.

        :param request: Http request object.
        :param obj: Object for which to check change permission.
        :return: False always.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """ Disable ability to delete EULAs through the admin interface.

        :param request: Http request object.
        :param obj: Object for which to check delete permission.
        :return: False always.
        """
        return False

    _list_display = ['timestamp', 'status']
    list_display = _list_display
    list_display_links = _list_display
    ordering = ['-timestamp']
