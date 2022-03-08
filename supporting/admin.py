from django.contrib import admin
from inheritable.admin import FdpInheritableAdmin, ArchivableAdmin, HostOnlyAdmin
from .models import State, Trait, PersonRelationshipType, County, Location, PersonIdentifierType, Title, \
    GroupingRelationshipType, PersonGroupingType, IncidentLocationType, EncounterReason, IncidentTag, \
    PersonIncidentTag, Allegation, AllegationOutcome, ContentType, Court, ContentIdentifierType, ContentCaseOutcome, \
    AttachmentType, TraitType, LeaveStatus, SituationRole


@admin.register(
    State, TraitType, PersonIdentifierType, Title, PersonGroupingType, IncidentLocationType, EncounterReason,
    IncidentTag, PersonIncidentTag, AllegationOutcome, ContentType, Court, ContentIdentifierType, ContentCaseOutcome,
    AttachmentType, LeaveStatus, SituationRole, Allegation
)
class SupportingAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for classes defined in the supporting app, which have only a name attribute.

    """
    _list_display = ['name'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = [] + ArchivableAdmin.list_filter
    search_fields = ['name']
    ordering = ['name']


@admin.register(PersonRelationshipType, GroupingRelationshipType)
class SupportingRelationshipTypeAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for relationship type classes defined in the supporting app.

    """
    _list_display = ['name', 'hierarchy'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['hierarchy'] + ArchivableAdmin.list_filter
    search_fields = ['name']
    ordering = ['name']


@admin.register(Trait)
class TraitAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for traits.

    """
    _list_display = ['type', 'name'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['type'] + ArchivableAdmin.list_filter
    search_fields = ['type__name', 'name']
    ordering = ['type__name', 'name']


@admin.register(County)
class CountyAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for counties.

    """
    _list_display = ['state', 'name'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['state'] + ArchivableAdmin.list_filter
    search_fields = ['state__name', 'name']
    ordering = ['state__name', 'name']


@admin.register(Location)
class LocationAdmin(HostOnlyAdmin, ArchivableAdmin):
    """ Admin interface for locations.

    """
    _list_display = ['county', 'address'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['county'] + ArchivableAdmin.list_filter
    search_fields = ['county__state__name', 'county__name', 'address']
    ordering = ['county__state__name', 'county__name', 'address']
