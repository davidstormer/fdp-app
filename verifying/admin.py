from django.contrib import admin
from inheritable.admin import HostOnlyAdmin, ArchivableAdmin
from .models import VerifyType, VerifyPerson, VerifyContentCase


@admin.register(VerifyType)
class VerifyTypeAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for types of verifications.

    """
    _list_display = ['name'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = [] + ArchivableAdmin.list_filter
    search_fields = ['name']
    ordering = ['name']


@admin.register(VerifyPerson)
class VerifyPersonAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for person verifications.

    """
    _list_display = ['type', 'person', 'fdp_user'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['type'] + ArchivableAdmin.list_filter
    search_fields = ['person__name', 'fdp_user__email']
    ordering = ['type__name', 'person__name', 'fdp_user__email']


@admin.register(VerifyContentCase)
class VerifyPersonAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for case content verifications.

    """
    _list_display = ['type', 'content_case', 'fdp_user'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['type'] + ArchivableAdmin.list_filter
    search_fields = ['fdp_user__email']
    ordering = ['type__name', 'fdp_user__email']
