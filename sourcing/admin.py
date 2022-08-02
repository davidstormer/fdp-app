from django.contrib import admin
from inheritable.admin import FdpInheritableAdmin, ArchivableAdmin, ConfidentiableAdmin
from .models import Attachment, Content, ContentCase, ContentIdentifier, ContentPerson, ContentPersonAllegation, \
    ContentPersonPenalty


@admin.register(Attachment)
class AttachmentAdmin(FdpInheritableAdmin, ConfidentiableAdmin):
    """ Admin interface for attachments.

    """
    _list_display = ['name', 'file_name', 'link'] + ConfidentiableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['extension', 'type'] + ConfidentiableAdmin.list_filter
    search_fields = ['name', 'file', 'extension', 'link']
    ordering = ['name', 'type']


@admin.register(Content)
class ContentAdmin(FdpInheritableAdmin, ConfidentiableAdmin):
    """ Admin interface for contents.

    """
    _list_display = [
                       'type', 'publication_date', 'name', 'link'
                   ] + ConfidentiableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['type'] + ConfidentiableAdmin.list_filter
    search_fields = ['name']
    ordering = ['type__name', 'publication_date']


@admin.register(ContentCase)
class ContentCaseAdmin(FdpInheritableAdmin, ArchivableAdmin):
    """ Admin interface for case contents.

    """
    _list_display = [
                        'outcome', 'court', 'settlement_amount', 'date_span_str', 'truncated_description'
                    ] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['outcome', 'court'] + ContentCase.list_filter_fields + ArchivableAdmin.list_filter
    search_fields = ['description']
    ordering = ['outcome__name', 'court__name'] + ContentCase.order_by_date_fields


@admin.register(ContentIdentifier)
class ContentIdentifierAdmin(FdpInheritableAdmin, ConfidentiableAdmin):
    """ Admin interface for content identifiers.

    """
    _list_display = ['content_identifier_type', 'identifier', 'content'] + ConfidentiableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['content_identifier_type'] + ConfidentiableAdmin.list_filter
    search_fields = ['identifier']
    ordering = ['content_identifier_type__name', 'identifier']


@admin.register(ContentPerson)
class ContentPersonAdmin(FdpInheritableAdmin, ArchivableAdmin):
    """ Admin interface for content persons.

    """
    _list_display = ['person', 'situation_role', 'content', 'is_guess'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['situation_role', 'is_guess'] + ArchivableAdmin.list_filter
    search_fields = ['person__name']
    ordering = ['person__name', 'situation_role__name']


@admin.register(ContentPersonAllegation)
class ContentPersonAllegationAdmin(FdpInheritableAdmin, ArchivableAdmin):
    """ Admin interface for allegations against persons linked to contents.

    """
    _list_display = [
                       'content_person', 'allegation', 'allegation_outcome', 'allegation_count'
                   ] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = ['allegation', 'allegation_outcome'] + ArchivableAdmin.list_filter
    search_fields = ['content_person__person__name', 'content_person__content__description']
    ordering = ['content_person__person__name']


@admin.register(ContentPersonPenalty)
class PenaltyAdmin(FdpInheritableAdmin, ArchivableAdmin):
    """ Admin interface for penalties for allegations against persons involved in incidents.

    """
    _list_display = ['content_person', 'penalty_requested', 'penalty_received'] + ArchivableAdmin.list_display
    list_display = _list_display
    list_display_links = _list_display
    list_filter = [] + ArchivableAdmin.list_filter
    search_fields = ['content_person__person__name', 'penalty_requested', 'penalty_received']
    ordering = ['content_person__person__name', 'discipline_date', 'penalty_requested', 'penalty_received']
