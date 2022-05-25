import json
import os
from pathlib import Path

import tablib
from django.core.files import File
from django.utils import timezone
from import_export import resources, fields
from import_export.fields import Field
from import_export.resources import ModelResource
from import_export.results import RowResult
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from bulk.models import BulkImport
from bulk_data_manipulation.common import get_record_from_external_id
from importer_narwhal.models import ImportBatch, ImportedRow, ErrorRow
from importer_narwhal.widgets import BooleanWidgetValidated
from wholesale.models import ModelHelper

# The mother list of models to be able to import to.
# The options in the interface are based on this.
MODEL_ALLOW_LIST = [
    # From the 'sourcing' app
    'Attachment',
    'Content',
    'ContentIdentifier',
    'ContentCase',
    'ContentPerson',
    'ContentPersonAllegation',
    'ContentPersonPenalty',
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
    # From the 'supporting' app
    'State',
    'County',
    'Location',
    'Court',
    'Trait',
    'TraitType',
]


class FdpModelResource(ModelResource):
    """Customized django-import-export ModelResource
    """
    external_id = Field()

    # On export retrieve external id of record and fill it into the 'external_id' column
    def dehydrate_external_id(self, record):
        try:
            bulk_import_records = \
                BulkImport.objects.filter(
                    table_imported_to=record.__class__.get_db_table(),
                    pk_imported_to=record.pk)
            # Handle multiple external ids pointing to the same record
            external_ids = []
            [external_ids.append(bulk_import.pk_imported_from) for bulk_import in bulk_import_records]
            return ','.join(external_ids)
        except BulkImport.DoesNotExist:
            return ''

    class Meta:
        skip_unchanged = True


# Some of the stock widgets don't meet our needs
# Override them with our custom versions
FdpModelResource.WIDGETS_MAP['BooleanField'] = \
    BooleanWidgetValidated


def get_data_model_from_name(model_name):
    app_name = ModelHelper.get_app_name(model=model_name)
    model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model_name)
    return model_class


# We'll need a mapping of FDP data models and their corresponding
# django-import-export resource. This creates it:
def _compile_resources():
    import_export_resources = {}

    for model_name in MODEL_ALLOW_LIST:
        model_class = get_data_model_from_name(model_name)

        resource = resources. \
            modelresource_factory(
                model=model_class, resource_class=FdpModelResource)
        import_export_resources[model_name] = resource
    return import_export_resources


resource_model_mapping = _compile_resources()


# Before import
#
#
# On import, locate relationship columns in external id form, and resolve the respective pk
def dereference_external_ids(resource_class, row, row_number=None, **kwargs):
    nonstandard_external_id_fields_mapping = {
        'subject_person': 'Person',
        'object_person': 'Person',
    }
    for model_name in MODEL_ALLOW_LIST:
        # Look for any fields that follow the pattern '[model name]__external' and dereference them to their pks
        try:
            external_id = row[f'{model_name.lower()}__external']
            model_class = get_data_model_from_name(model_name)
            referenced_record = get_record_from_external_id(model_class, external_id)
            row[model_name.lower()] = referenced_record.pk
        except KeyError:
            pass
        # Look for any fields that follow the pattern '[model name]s__external' (plural) and dereference them to their
        # pks
        try:
            external_id = row[f'{model_name.lower()}s__external']
            model_class = get_data_model_from_name(model_name)
            referenced_record = get_record_from_external_id(model_class, external_id)
            row[model_name.lower() + 's'] = referenced_record.pk
        except KeyError:
            pass
    for field_name in nonstandard_external_id_fields_mapping.keys():
        # Look for any fields from the other external id fields above and dereference them to their pks
        try:
            external_id = row[f'{field_name}__external']
            model_class = get_data_model_from_name(nonstandard_external_id_fields_mapping[field_name])
            referenced_record = get_record_from_external_id(model_class, external_id)
            row[field_name] = referenced_record.pk
        except KeyError:
            pass


# Modify the before_import_row hook with our custom transformations
def before_import_row(resource_class, row, row_number=None, **kwargs):
    dereference_external_ids(resource_class, row, row_number, **kwargs)


# After import
#
#
# After import, generate the external id in the 'external_id' column
def import_external_id(resource_class, row, row_result, row_number, **kwargs):
    # TODO: I think this should maybe be a 'get or create' logic, rather than just always create...?
    # If so, if there's a pk in the sheet too it should probably compare to the one in the BulkImport record,
    # and balk if there's an inconsistency?
    if row_result.import_type == row_result.IMPORT_TYPE_NEW:
        external_id = row.get('external_id', None)
        if external_id:
            model = resource_class.Meta.model
            # Check to see if external id already exists, raise an error if so
            found = BulkImport.objects.filter(
                table_imported_to=model.get_db_table(),
                pk_imported_from=external_id
            )
            if len(found) > 0:
                raise Exception(f"External ID already exists: {model}:{external_id}")
            # If doesn't exist go ahead and create it
            BulkImport.objects.create(
                table_imported_to=model.get_db_table(),
                pk_imported_to=row_result.object_id,
                pk_imported_from=external_id,
                data_imported=json.dumps(dict(row))
            )


def after_import_row(resource_class, row, row_result, row_number=None, **kwargs):
    import_external_id(resource_class, row, row_result, row_number, **kwargs)


# Amend the resources in the map by applying the above pre and post import customizations
for resource in resource_model_mapping.keys():
    resource_model_mapping[resource].before_import_row = before_import_row
    resource_model_mapping[resource].after_import_row = after_import_row


# Setup FDP 'types & tags' fields
#
#
foreign_key_fields_get_or_create = \
    {
        'Attachment': ['type', ],
        'PersonIdentifier': ['person_identifier_type', ],
        'PersonRelationship': ['type', ],
        'Content': ['type', ],
        'ContentPerson': ['situation_role', ],
        'Trait': ['type', ],
        'PersonTitle': ['title', ],
        'PersonPayment': ['leave_status', ],  # No county because it requires a state value
        'PersonGrouping': ['type', ],
    }

foreign_key_fields_get_only = \
    {
        'PersonPayment': ['county', ],
        'Grouping': ['counties', ],
    }

many_to_many_fields_get_only = \
    {
        'Person': ['traits', ],
    }


# The stock foreign key widget doesn't create records if they don't exist
# Create a new custom widget that does this
class ForeignKeyWidgetGetOrCreate(ForeignKeyWidget):
    # c.f. https://stackoverflow.com/questions/32369984/django-import-export-new-values-in-foriegn-key-model
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            try:
                return self.get_queryset(value, row, *args, **kwargs).get(**{self.field: value})
            except self.model.DoesNotExist:
                return self.model.objects.create(name=value)
        else:
            return None

    def get_help_html(self):
        return f"""Accepts <code>{ self.model.__name__ }</code> { self.field }s rather than PKs by default.
        Accepts external ids using <code>__external</code> extension.
        """

import import_export


def foreign_key_widget_help_html(self):
    if self.field == 'pk':
        return f"""References <code>{self.model.__name__}</code> by pk. Accepts external ids using 
        <code>__external</code> extension."""
    elif self.field == 'name':
        return f"""Accepts <code>{ self.model.__name__ }</code> { self.field }s rather than PKs by default.
        Accepts external ids using <code>__external</code> extension.
        """


import_export.widgets.ForeignKeyWidget.get_help_html = foreign_key_widget_help_html


def many_to_many_widget_help_html(self):
    if self.field == 'pk':
        return f"""References <code>{self.model.__name__}</code> by pk. Accepts external ids using 
        <code>__external</code> extension."""
    elif self.field == 'name':
        return f"""Accepts <code>{ self.model.__name__ }</code> { self.field }s rather than PKs by default.
        Accepts external ids using <code>__external</code> extension.
        """


import_export.widgets.ManyToManyWidget.get_help_html = many_to_many_widget_help_html


# Customize the 'type' fields to use the new ForeignKeyWidgetGetOrCreate widget
def apply_custom_widgets(target_fields, widget):
    # For every supported model
    for model_name in resource_model_mapping.keys():
        # Go through each field
        for field_name in resource_model_mapping[model_name].fields.keys():
            # If one of them is on the list of fields to customize...
            for get_or_create_foreign_key_field in target_fields.get(model_name, []):
                if get_or_create_foreign_key_field == field_name:
                    # Customize the field with the ForeignKeyWidgetGetOrCreate widget
                    foreign_key_model = get_data_model_from_name(model_name)._meta.get_field(field_name).remote_field.model
                    resource_model_mapping[model_name].fields[field_name] = fields.Field(
                        column_name=field_name,
                        attribute=field_name,
                        widget=widget(
                            model=foreign_key_model,
                            field='name'  # <- Assumes that the 'natural' key is in the 'name' field
                                    # may need to be factored into get_or_create_foreign_key_fields
                                    # in the future to handle other fields.
                        )
                    )


# Set up 'type' fields (foreign key one to many)
apply_custom_widgets(foreign_key_fields_get_or_create, ForeignKeyWidgetGetOrCreate)
apply_custom_widgets(foreign_key_fields_get_only, ForeignKeyWidget)

# Set up "tag" fields (m2m) -- for now not 'get or create' just get
apply_custom_widgets(many_to_many_fields_get_only, ManyToManyWidget)

# Nice error reports
#
#


# Define data models for holding the error report data from an import that was run
class ErrorReportRow:
    def __init__(self, row_number: int, error_message: str, row_data: str):
        self.row_number = row_number
        self.error_message = error_message
        self.row_data = row_data

    def __repr__(self):
        return f"{self.row_number} | {self.error_message} | {self.row_data}"


class ImportedReportRow:
    # Row number, action, error (bool), info (error message or diff), pk, repr / link
    def __init__(self, row_number: int, action: str, error: bool, info: str, pk, name: str):
        self.row_number = row_number
        self.action = action
        self.error = error
        self.info = info
        self.pk = pk
        self.name = name

    def __str__(self):
        return f"{self.row_number} | {self.action} | {self.error} | {self.pk} | {self.name}"


class ImportReport:
    def __init__(self):
        self.validation_errors = []
        self.database_errors = []
        self.imported_records = []

    def __str__(self):
        return f"""
        validation_errors: {len(self.validation_errors)}
        database_errors: {len(self.database_errors)}
        """


def clean_diff_html(diff_html: str) -> str:
    return diff_html.replace(' style="background:#e6ffe6;"', '') \
        .replace(' style="background:#ffe6e6;"', '')


def do_import_from_disk(model_name: str, input_file: str):
    """Creates and import batch from a csv file located on the local disk, and then runs it.
    Used by management commands and tests. Not intended for use by web views.
    """
    batch_record = ImportBatch.objects.create()
    batch_record.target_model_name = model_name
    batch_record.submitted_file_name = os.path.basename(input_file)
    path = Path(input_file)
    with path.open(mode='rb') as f:
        batch_record.import_sheet = File(f, name=path.name)
        batch_record.save()
    return run_import_batch(batch_record)


def do_dry_run(batch_record):
    batch_record.dry_run_started = timezone.now()
    batch_record.save()
    import_sheet_raw = batch_record.import_sheet.file.open().read().decode("utf-8")
    input_sheet = tablib.Dataset().load(import_sheet_raw, "csv")
    # Re "csv" fixes error/bug "Tablib has no format 'None' or it is not registered."
    # https://github.com/jazzband/tablib/issues/502
    resource_class = resource_model_mapping[batch_record.target_model_name]
    resource = resource_class()
    result = resource.import_data(input_sheet, dry_run=True)
    batch_record.number_of_rows = len(result.rows)
    import_report = ImportReport()

    # django-import-export uses the dry-run pattern to first flush out validation errors, and then in a second step
    # encounter any database level errors. We'll apply this pattern here:
    if result.has_validation_errors():
        batch_record.errors_encountered = True
        batch_record.save()
        for row_num, row in enumerate(result.rows):
            ImportedRow.objects.create(
                row_number=row_num,
                import_batch=batch_record,
                action=row.import_type,
                errors=row.validation_error,
                info=clean_diff_html(str(row.diff)),
                imported_record_name=row.object_repr,
                imported_record_pk=row.object_id,
            )
        for invalid_row in result.invalid_rows:
            # Nice error reports continued...
            ErrorRow.objects.create(
                import_batch=batch_record,
                row_number=invalid_row.number,
                error_message=str(invalid_row.error_dict),
                row_data=str(invalid_row.values)
            )
            import_report.validation_errors.append(
                ErrorReportRow(invalid_row.number, str(invalid_row.error_dict), str(invalid_row.values))
            )
    batch_record.dry_run_completed = timezone.now()
    batch_record.save()


# The business
def run_import_batch(batch_record):
    """Main api interface for narwhal importer
    """
    batch_record.started = timezone.now()
    batch_record.save()
    import_sheet_raw = batch_record.import_sheet.file.open().read().decode("utf-8")
    input_sheet = tablib.Dataset().load(import_sheet_raw, "csv")
    # Re "csv" fixes error/bug "Tablib has no format 'None' or it is not registered."
    # https://github.com/jazzband/tablib/issues/502
    resource_class = resource_model_mapping[batch_record.target_model_name]
    resource = resource_class()
    result = resource.import_data(input_sheet, dry_run=True)
    batch_record.number_of_rows = len(result.rows)
    import_report = ImportReport()

    # django-import-export uses the dry-run pattern to first flush out validation errors, and then in a second step
    # encounter any database level errors. We'll apply this pattern here:
    if result.has_validation_errors():
        batch_record.errors_encountered = True
        batch_record.save()
        for invalid_row in result.invalid_rows:
            # Nice error reports continued...
            ErrorRow.objects.create(
                import_batch=batch_record,
                row_number=invalid_row.number,
                error_message=str(invalid_row.error_dict),
                row_data=str(invalid_row.values)
            )
            import_report.validation_errors.append(
                ErrorReportRow(invalid_row.number, str(invalid_row.error_dict), str(invalid_row.values))
            )
            batch_record.completed = timezone.now()
            batch_record.save()
    else:  # We're safe to proceed with live rounds
        result = resource.import_data(input_sheet, dry_run=False)
        if result.has_errors():
            batch_record.errors_encountered = True
            batch_record.save()
            for error_row in result.row_errors():
                row_num = error_row[0]
                errors = error_row[1]
                for error in errors:
                    # Nice error reports continued...
                    ErrorRow.objects.create(
                        import_batch=batch_record,
                        row_number=row_num,
                        error_message=str(error.error),
                        row_data=str(dict(error.row))
                    )
                    import_report.database_errors.append(
                        ErrorReportRow(row_num, str(error.error), str(dict(error.row)))
                    )
                    batch_record.completed = timezone.now()
                    batch_record.save()
        else:
            batch_record.errors_encountered = False
            for row_num, row in enumerate(result.rows):
                ImportedRow.objects.create(
                    row_number=row_num,
                    import_batch=batch_record,
                    action=row.import_type,
                    errors=row.validation_error,
                    info=clean_diff_html(str(row.diff)),
                    imported_record_name=row.object_repr,
                    imported_record_pk=row.object_id,
                )
                import_report.imported_records.append(
                    ImportedReportRow(
                        row_num,
                        row.import_type,
                        row.validation_error,
                        row.diff,
                        row.object_id,
                        row.object_repr)
                )
            batch_record.completed = timezone.now()
            batch_record.save()

    return import_report


def do_export(model_name, file_name):
    resource_class = resource_model_mapping[model_name]
    model_resource = resource_class()
    data_set = model_resource.export()
    with open(file_name, 'w') as fd:
        fd.write(data_set.csv)


class BatchDeleteFoundUpdates(Exception):
    pass


def delete_batch(batch_number: str or int) -> list:
    batch = ImportBatch.objects.get(pk=batch_number)
    # Check to make sure there aren't any updates in the batch
    for row in batch.imported_rows.all():
        if row.action == 'update':
            raise BatchDeleteFoundUpdates('Updates in batch. Cannot delete batch.')

    # Now delete
    model = get_data_model_from_name(batch.target_model_name)
    not_found = []
    for row in batch.imported_rows.all():
        try:
            record = model.objects.get(pk=row.imported_record_pk)
            record.delete()
        except model.DoesNotExist:
            not_found.append(f"{model}:{row.pk}")
        try:
            bi_record = BulkImport.objects.get(
                table_imported_to=model.get_db_table(),
                pk_imported_to=row.imported_record_pk
            )
            bi_record.delete()
        except Exception as e:
            not_found.append(f"{model}:{row.pk} {e}")
    return not_found
