from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.html import format_html
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from data_wizard.models import Identifier, Run
from data_wizard.sources.models import FileSource
from inheritable.models import AbstractFileValidator


class BulkImport(models.Model):
    """ Bulk data imports that have been performed on FDP.

    Used to record an audit trail during a data migration.

    Attributes:
        :source_imported_from (str): External source, such as an earlier version of the FDP database, from which data
        was imported.
        :table_imported_from (str): Table in external source from which data was imported.
        :pk_imported_from (str): Primary key in external source uniquely identifying data that was imported.
        :table_imported_to (str): Table in FDP to which data was imported.
        :pk_imported_to (int): Primary key in FDP uniquely identifying data that was imported.
        :data_imported (json): JSON representation of data that was imported.
        :timestamp (datetime): Automatically added timestamp recording when imported was performed.
        :notes (str): Explanatory notes for the import.
    """
    source_imported_from = models.CharField(
        null=False,
        blank=False,
        help_text=_('External source, such as an earlier version of the FDP database, from which data was imported.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('Source')
    )

    table_imported_from = models.CharField(
        null=False,
        blank=True,
        help_text=_('Table in external source from which data was imported.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('Source table')
    )

    pk_imported_from = models.CharField(
        null=False,
        blank=False,
        help_text=_('Primary key in external source uniquely identifying data that was imported.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('Source primary key')
    )

    table_imported_to = models.CharField(
        null=False,
        blank=False,
        help_text=_('Table in FDP to which data was imported.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('FDP table')
    )

    pk_imported_to = models.IntegerField(
        null=False,
        blank=False,
        help_text=_('Primary key in FDP uniquely identifying data that was imported.'),
        validators=[MinValueValidator(0)],
        verbose_name=_('FDP primary key')
    )

    data_imported = models.JSONField(
        blank=False,
        null=False,
        help_text=_('JSON representation of data that was imported.'),
        verbose_name=_('Imported data')
    )

    timestamp = models.DateTimeField(
        null=False,
        blank=False,
        auto_now_add=True,
        help_text=_('Automatically added timestamp recording when import was performed.'),
        verbose_name=_('timestamp')
    )

    notes = models.TextField(
        null=False,
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Explanatory notes for the import.'),
    )

    #: Default manager
    objects = models.Manager()

    def __str__(self):
        """Defines string representation for a bulk import.

        :return: String representation of a bulk import.
        """
        return '{i} {a}{b} {c} {t} {d} {e} {f}'.format(
            i=_('imported from'),
            a=self.source_imported_from,
            b='' if not self.table_imported_from else ' {b}'.format(b=self.table_imported_from),
            c='{i}{p}'.format(i=_('ID#'), p=self.pk_imported_from),
            t=_('to'),
            d=self.table_imported_to,
            e='{i}{p}'.format(i=_('ID#'), p=self.pk_imported_to),
            f='{a} {t}'.format(a=_('at'), t=self.timestamp)
        )

    @classmethod
    def filter_for_admin(cls, queryset, user):
        """ Filter a queryset for the admin interfaces.

        Assumes that queryset has already been filtered for direct confidentiality, i.e. whether user has access to
        each record based on the record's level of confidentiality. E.g. a confidentiable queryset of Person.

        Can be used to filter for indirect confidentiality, i..e whether user has access to each record based on other
        relevant records' levels of confidentiality. E.g. a queryset of PersonAlias linking to a confidentiality
        queryset of Person.

        :param queryset: Queryset to filter.
        :param user: User for which to filter queryset.
        :return: Filtered queryset.
        """
        # only host administrators and super users can access the queryset
        return queryset if (user.is_host and user.is_administrator) or user.is_superuser else cls.objects.none()

    class Meta:
        db_table = '{d}bulk_import'.format(d=settings.DB_PREFIX)
        verbose_name = _('Bulk import log')
        verbose_name_plural = _('Bulk import logs')
        ordering = ['timestamp', 'table_imported_to', 'pk_imported_to']
        indexes = [
            models.Index(fields=['table_imported_to', 'pk_imported_from', 'pk_imported_to']),
        ]


class IsHostAdminUser(BasePermission):
    """ Restricts data import access only to administrator users belonging to a host organization.

        Used in the settings by the data wizard package, i.e.

        # Django Data Wizard: https://github.com/wq/django-data-wizard
        DATA_WIZARD = {
            ...
            'PERMISSION': 'bulk.models.IsHostAdminUser',
            ...
        }

    """
    def has_permission(self, request, view):
        """ Checks whether a user has administrator access and belongs to a host organization.

        :param request: HTTP request sent by user.
        :param view: Ignored.
        :return: True if user is an administrator and belongs to a host organization, false otherwise.
        """
        return bool(request.user and request.user.is_authenticated and request.user.has_import_access)


class FdpImportFile(FileSource):
    """ Files that have been uploaded for import (or have already been imported) through the Django Data Wizard package.

        See: https://github.com/wq/django-data-wizard

        Attributes:
            :file (file): File uploaded for import through the Django Data Wizard package.

    """
    #: Default manager
    objects = models.Manager()

    def clean(self):
        """ Ensure that the FDP import file path contains no directory traversal.

        :return: Nothing
        """
        super(FdpImportFile, self).clean()
        # full path when relative and root paths are joined
        full_path = AbstractFileValidator.join_relative_and_root_paths(
            relative_path=self.file,
            root_path=settings.MEDIA_ROOT
        )
        # verify that path is a real path (i.e. no directory traversal takes place)
        # will raise exception if path is not a real path
        AbstractFileValidator.check_path_is_expected(
            relative_path=self.file,
            root_path=settings.MEDIA_ROOT,
            expected_path_prefix=full_path,
            err_msg=_('Fdp import file path may contain directory traversal'),
            err_cls=ValidationError
        )

    class Meta:
        db_table = '{d}import_file'.format(d=settings.DB_PREFIX)
        verbose_name = _('Import file')
        verbose_name_plural = _('Import files')
        ordering = ['-date', 'name', 'file']


class FdpImportMapping(models.Model):
    """ Import mappings are one-to-one relationships with instances of the Identifier model class, acting as a wrapper
    for easy management.

    Identifier model class instances are mappings between columns in the files to import and available columns in the
    serializers defined using the Django Data Wizard package.

    See: https://github.com/wq/django-data-wizard

    Attributes:
        :identifier (o2o): Instance of the Identifier model class to which this import mapping is linked.

    Properties:
        :serializer (str): Retrieves the name of the serializer in the column mapping.
        :column_to_import (str): Retrieves the name of the column in the file to import in the column mapping.

    """
    identifier = models.OneToOneField(
        Identifier,
        on_delete=models.CASCADE,
        related_name='fdp_import_mapping',
        related_query_name='fdp_import_mapping',
        null=False,
        blank=False,
        help_text=_('Instance of the Identifier model class that was defined in the Django Data Wizard package.'),
        verbose_name=_('Identifier')
    )

    #: Default manager
    objects = models.Manager()

    @staticmethod
    def parse_serializer_name(serializer):
        """ Parse the name of the serializer by removing the app and module name.

        :param serializer: Full name of serializer to parse.
        :return: Parsed name of serializer.
        """
        return str(serializer).lstrip('bulk.serializers.')

    @classmethod
    def filter_for_admin(cls, queryset, user):
        """ Filter a queryset for the admin interfaces.

        Assumes that queryset has already been filtered for direct confidentiality, i.e. whether user has access to
        each record based on the record's level of confidentiality. E.g. a confidentiable queryset of Person.

        Can be used to filter for indirect confidentiality, i..e whether user has access to each record based on other
        relevant records' levels of confidentiality. E.g. a queryset of PersonAlias linking to a confidentiality
        queryset of Person.

        :param queryset: Queryset to filter.
        :param user: User for which to filter queryset.
        :return: Filtered queryset.
        """
        # only host administrators and super users can access the queryset
        return queryset if (user.is_host and user.is_administrator) or user.is_superuser else cls.objects.none()

    @property
    def serializer(self):
        """ Retrieves the name of the serializer in the column mapping.

        :return: Name of serializer.
        """
        serializer = getattr(self.identifier, 'serializer', _('Unknown'))
        return self.parse_serializer_name(serializer=serializer)

    @property
    def column_to_import(self):
        """ Retrieves the name of the column in the file to import in the column mapping.

        :return: Name of column in the file to import.
        """
        return getattr(self.identifier, 'name', _('Unknown'))

    class Meta:
        db_table = '{d}import_mapping'.format(d=settings.DB_PREFIX)
        verbose_name = _('Import column mapping')
        verbose_name_plural = _('Import column mappings')
        ordering = ['identifier__serializer', 'identifier__name']


class FdpImportRun(models.Model):
    """ Import runs are one-to-one relationships with instances of the Run model class, acting as a wrapper
    for easy management.

    Run model class instances are encapsulations of an import process performed using the Django Data Wizard package.

    See: https://github.com/wq/django-data-wizard

    Attributes:
        :run (o2o): Instance of the Run model class to which this import run is linked.

    Properties:
        :serializer (str): Retrieves the name of the serializer in the import run.
        :last_update (datetime): Retrieves the last update date/time for the import run.
        :record_count (int): Retrieves the number of records imported during the run.
        :log_link (str): HTML that links to the list of records that were imported during the run.
    """
    run = models.OneToOneField(
        Run,
        on_delete=models.CASCADE,
        related_name='fdp_import_run',
        related_query_name='fdp_import_run',
        null=False,
        blank=False,
        help_text=_('Instance of the Run model class that was defined in the Django Data Wizard package.'),
        verbose_name=_('Run')
    )

    #: Default manager
    objects = models.Manager()

    @staticmethod
    def parse_serializer_name(serializer):
        """ Parse the name of the serializer by removing the app and module name.

        :param serializer: Full name of serializer to parse.
        :return: Parsed name of serializer.
        """
        return str(serializer).lstrip('bulk.serializers.')

    @classmethod
    def filter_for_admin(cls, queryset, user):
        """ Filter a queryset for the admin interfaces.

        Assumes that queryset has already been filtered for direct confidentiality, i.e. whether user has access to
        each record based on the record's level of confidentiality. E.g. a confidentiable queryset of Person.

        Can be used to filter for indirect confidentiality, i..e whether user has access to each record based on other
        relevant records' levels of confidentiality. E.g. a queryset of PersonAlias linking to a confidentiality
        queryset of Person.

        :param queryset: Queryset to filter.
        :param user: User for which to filter queryset.
        :return: Filtered queryset.
        """
        # only host administrators and super users can access the queryset
        return queryset if (user.is_host and user.is_administrator) or user.is_superuser else cls.objects.none()

    @property
    def serializer(self):
        """ Retrieves the name of the serializer for this particular import run.

        :return: Name of serializer.
        """
        serializer = getattr(self.run, 'serializer', _('Unknown'))
        return self.parse_serializer_name(serializer=serializer)

    @property
    def last_update(self):
        """ Retrieves the last update date/time for this particular import run.

        :return: Last update date/time.
        """
        return getattr(self.run, 'last_update', None)

    @property
    def record_count(self):
        """ Retrieves the number of records that were imported during this particular run.

        :return: Number of records.
        """
        return getattr(self.run, 'record_count', 0)

    @property
    def log_link(self):
        """ Retrieves the HTML that links to the list of records that were imported during this particular run.

        :return: HTML that links to the list of records.
        """
        run_pk = getattr(self.run, 'pk', 0)
        link = '/datawizard/{i}/records/'.format(i=run_pk)
        return format_html('<a href="{link}">{link}</a>'.format(link=link))

    class Meta:
        db_table = '{d}import_run'.format(d=settings.DB_PREFIX)
        verbose_name = _('Import run')
        verbose_name_plural = _('Import runs')
        ordering = ['run__serializer']
