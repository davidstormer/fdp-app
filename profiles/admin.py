from django.contrib import admin
from .models import OfficerSearch, OfficerView, CommandSearch, CommandView
from inheritable.admin import HostOnlyAdmin


@admin.register(OfficerSearch)
class OfficerSearchAdmin(HostOnlyAdmin):
    """ Admin interface for officer searches performed by FDP users.

    """
    readonly_fields = [
        'fdp_user', 'parsed_search_criteria', 'timestamp', 'ip_address', 'num_of_results'
    ]
    _list_display = ['timestamp', 'fdp_user', 'ip_address']
    list_display = _list_display
    list_display_links = _list_display
    ordering = ['timestamp']


@admin.register(OfficerView)
class OfficerViewAdmin(HostOnlyAdmin):
    """ Admin interface for officer profiles viewed by FDP users.

    """
    readonly_fields = ['fdp_user', 'person', 'timestamp', 'ip_address']
    _list_display = ['timestamp', 'fdp_user', 'person']
    list_display = _list_display
    list_display_links = _list_display
    ordering = ['timestamp']


@admin.register(CommandSearch)
class CommandSearchAdmin(HostOnlyAdmin):
    """ Admin interface for comand searches performed by FDP users.

    """
    readonly_fields = [
        'fdp_user', 'parsed_search_criteria', 'timestamp', 'ip_address', 'num_of_results'
    ]
    _list_display = ['timestamp', 'fdp_user', 'ip_address']
    list_display = _list_display
    list_display_links = _list_display
    ordering = ['timestamp']


@admin.register(CommandView)
class CommandViewAdmin(HostOnlyAdmin):
    """ Admin interface for command profiles viewed by FDP users.

    """
    readonly_fields = ['fdp_user', 'grouping', 'timestamp', 'ip_address']
    _list_display = ['timestamp', 'fdp_user', 'grouping']
    list_display = _list_display
    list_display_links = _list_display
    ordering = ['timestamp']
