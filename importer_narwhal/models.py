from operator import attrgetter
from django.apps import apps
from django.contrib.postgres.fields import ArrayField
from django.db.models.fields.files import FieldFile
from django.template.defaultfilters import filesizeformat
from django.core.exceptions import ValidationError
from django.db import models
import os

from django.urls import reverse

# The mother list of models to be able to import to / export from.
# The options on the UI come from this.
MODEL_ALLOW_LIST = [
    # From the 'core' app
    'Person',
    'PersonContact',
    'PersonAlias',
    'PersonPhoto',
    'PersonIdentifier',
    'PersonTitle',
    'PersonRelationship',
    'PersonPayment',
    'Grouping',
    'GroupingAlias',
    'GroupingRelationship',
    'PersonGrouping',
    'Incident',
    'PersonIncident',
    'GroupingIncident',
    # From the 'sourcing' app
    'Attachment',
    'Allegation',
    'AllegationOutcome',
    'Content',
    'ContentIdentifier',
    'ContentCase',
    'ContentCaseOutcome',
    'ContentIdentifierType',
    'ContentPerson',
    'ContentPersonAllegation',
    'ContentPersonPenalty',
    'EncounterReason',
    'GroupingRelationshipType',
    'IncidentLocationType',
    'IncidentTag',
    'PersonIncidentTag',
    # From the 'supporting' app
    'State',
    'County',
    'Location',
    'Court',
    'Trait',
    'TraitType',
]


class ModelHelper:
    """ Abstract class defining constants and methods used to load and process models from various apps.
    """
    #: Name of 'sourcing' app that contains relevant models.
    __sourcing_app_name = 'sourcing'

    #: Name of 'core' app that contains relevant models.
    __core_app_name = 'core'

    #: Name of 'supporting' app that contains relevant models.
    __supporting_app_name = 'supporting'

    #: Name of attribute storing model name as a string representation.
    __model_name_attribute = '__name__'

    @staticmethod
    def __get_model_options(model):
        """ Retrieves the options for a particular Django model.
        Uses the '_meta' attribute.
        :param model: Model for which to retrieve options.
        :return: Object representing options for model.
        """
        return getattr(model, '_meta')

    @staticmethod
    def __get_models(app):
        """ Retrieves a list of models for a specific app.
        :param app: App for which to retrieve list of models.
        :return: List of models for app.
        """
        return list(apps.get_app_config(app).get_models())

    @classmethod
    def __get_sourcing_models(cls):
        """ Retrieves list of models for 'sourcing' app.
        :return: List of models in 'sourcing' app.
        """
        return cls.__get_models(app=cls.__sourcing_app_name)

    @classmethod
    def __get_core_models(cls):
        """ Retrieves list of models for 'core' app.
        :return: List of models in 'core' app.
        """
        return cls.__get_models(app=cls.__core_app_name)

    @classmethod
    def __get_supporting_models(cls):
        """ Retrieves list of models for 'supporting' app.
        :return: List of models in 'supporting' app.
        """
        return cls.__get_models(app=cls.__supporting_app_name)

    @classmethod
    def get_app_name(cls, model):
        # check if model is in the sourcing app
        if model in map(attrgetter(cls.__model_name_attribute), cls.__get_sourcing_models()):
            app_name = cls.__sourcing_app_name
        # check if model is in the core app
        elif model in map(attrgetter(cls.__model_name_attribute), cls.__get_core_models()):
            app_name = cls.__core_app_name
        # check if model is in the supporting app
        elif model in map(attrgetter(cls.__model_name_attribute), cls.__get_supporting_models()):
            app_name = cls.__supporting_app_name
        else:
            app_name = None
        return app_name

    @classmethod
    def get_model_class(cls, app_name, model_name):
        """ Retrieves the class for a model in an app.
        :param app_name: Name of app.
        :param model_name: Name of model.
        :return: Class for model in app.
        """
        return apps.get_model(app_label=app_name, model_name=model_name)


def validate_import_sheet_extension(file):
    allowed_extensions = ['csv']
    if isinstance(file, FieldFile):
        file = file.name
    extension = os.path.splitext(file)[1][1:].lower()
    if extension not in allowed_extensions:
        raise ValidationError(f'{extension} file not allowed. File must end in one of {allowed_extensions}')


def validate_import_sheet_file_size(file):
    max_file_size = 1e+7  # 10mb
    if file.size > max_file_size:
        raise ValidationError(f'File size {filesizeformat(file.size)} too large. File must be less than {filesizeformat(max_file_size)}.')


# TODO: turn started into created, and add another started that's not auto_now_add
class ImportBatch(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    dry_run_started = models.DateTimeField(null=True, blank=True)
    dry_run_completed = models.DateTimeField(null=True, blank=True)
    started = models.DateTimeField(null=True, blank=True)
    completed = models.DateTimeField(null=True, blank=True)
    target_model_name = models.CharField(choices=zip(MODEL_ALLOW_LIST, MODEL_ALLOW_LIST), max_length=256,
         help_text=f"""Select the data model that you would like to import to. Read more about appropriate mappings 
         on the Mappings page.""")
    number_of_rows = models.IntegerField(null=True)
    errors_encountered = models.BooleanField(null=True)
    submitted_file_name = models.CharField(max_length=1024)
    general_errors = models.TextField()
    import_sheet = models.FileField(
        upload_to='import-sheets/%Y/%m/%d/%H/%M/%S/',
        validators=[
            validate_import_sheet_extension,
            validate_import_sheet_file_size
        ],
        help_text="Must be CSV format, encoded in UTF-8"
    )

    def get_absolute_url(self):
        return reverse('importer_narwhal:batch', kwargs={'pk': self.pk})

    def __str__(self):
        # number, import time, filename, model, number of records,
        # and whether it succeeded or not.
        return f"{self.pk} | {self.started_fmt} | {self.completed_fmt} | {self.submitted_file_name} | " \
               f"{self.target_model_name} | {self.number_of_rows} | "\
               f"{'Errors encountered' if self.errors_encountered else 'No errors'}"

    @property
    def started_fmt(self):
        if self.started:
            return f"{self.started:%Y-%m-%d %H:%M:%S}"
        else:
            return "Not started yet"

    @property
    def completed_fmt(self):
        if self.started:
            return f"{self.completed:%Y-%m-%d %H:%M:%S}" if self.completed else 'Aborted'
        else:
            return "Not started yet"

    @property
    def state(self):
        state = ''

        # 'pre-validate' Batch newly created, ready to verify
        #   highlight "Validate" in stepper
        #   show button to verify
        if not self.dry_run_started and not self.started and not self.completed:
            state = 'pre-validate'

        # 'mid-validate' Currently running validation
        #   highlight "Validate" in stepper
        #   say we're in the middle of validation; show spinner
        #   don't show button to import
        elif self.dry_run_started \
                and not self.dry_run_completed:
            state = 'mid-validate'

        # 'post-validate-errors' Batch verified, problems, abort
        #   highlight "Validate" in stepper
        #   don't show button to import
        elif self.dry_run_completed \
                and self.errors_encountered \
                and not self.started:
            state = 'post-validate-errors'

        # 'post-validate-ready' Batch verified, no errors, ready to import
        #   highlight "Import" in stepper
        #   show button to import
        elif self.dry_run_completed \
                and not self.errors_encountered \
                and not self.started:
            state = 'post-validate-ready'

        # 'mid-import' Currently running import
        #   highlight "Import" in stepper
        #   say we're in the middle of importing; show spinner
        #   don't show button to import
        elif self.started and not self.completed:
            state = 'mid-import'

        # 'post-import-failed'
        elif self.completed and self.errors_encountered:
            state = 'post-import-failed'

        elif self.completed:
            state = 'complete'

        return state


class ImportedRow(models.Model):
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='imported_rows')
    row_number = models.IntegerField()
    action = models.CharField(max_length=128, null=True)
    errors = models.TextField(null=True)
    info = models.TextField(null=True)
    imported_record_pk = models.CharField(max_length=128, null=True)
    imported_record_name = models.CharField(max_length=1024, null=True)

    def __str__(self):
        return f"{self.row_number} | {self.action} | {self.errors} | {self.info} | {self.imported_record_name} | {self.imported_record_pk}"


class ErrorRow(models.Model):
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='error_rows')
    row_number = models.IntegerField()
    error_message = models.TextField()
    row_data = models.TextField()

    def __str__(self):
        return f"{self.row_number} | {self.error_message} | {self.row_data}"


class ExportBatch(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, blank=True)
    completed = models.DateTimeField(null=True, blank=True)
    models_to_export = ArrayField(
        models.CharField(max_length=256),
        help_text="Choose which data models to include in the export. Allows multiple."
    )
    export_file = models.FileField(upload_to='data-exports/', null=True, blank=True)

    def get_absolute_url(self):
        return f"/changing/importer/exports/{self.pk}"
