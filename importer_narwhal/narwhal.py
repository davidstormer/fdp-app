import json
import os
import re
from pathlib import Path

import tablib
from django.core.files import File
from django.utils import timezone
import import_export
from import_export import resources, fields
import import_export.fields
from import_export.resources import ModelResource
from import_export.results import RowResult
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from bulk.models import BulkImport
from bulk_data_manipulation.common import get_record_from_external_id
from core.models import PersonAlias, Person, Grouping, GroupingAlias, GroupingRelationship
from importer_narwhal.models import ImportBatch, ImportedRow, ErrorRow, MODEL_ALLOW_LIST
from importer_narwhal.widgets import BooleanWidgetValidated
from supporting.models import GroupingRelationshipType
from wholesale.models import ModelHelper


class ExternalIdField(fields.Field):
    def before_import_row(self, resource_class, row, row_number, **kwargs):
        for import_field_name in row.copy().keys():  # '.copy()' prevents 'OrderedDict mutated during iteration' exception
            if import_field_name.endswith('__external_id'):
                if row[import_field_name]:
                    destination_field_name = import_field_name[:-13]
                    model_class = resource_class.Meta.model._meta.get_field(destination_field_name).remote_field.model
                    referenced_record = get_record_from_external_id(model_class, row[import_field_name])
                    if resource_class.fields[destination_field_name].widget.field == 'name':
                        # Field expects a natural key value, not a pk:
                        row[destination_field_name] = referenced_record.name
                    else:
                        row[destination_field_name] = referenced_record.pk

    def after_import_row(self, resource_class, row, row_result, row_number, **kwargs):
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

    def get_help_html(self):
        return """Use the <code>external_id</code> column to create an external id on import, or refer to an existing 
        record to update it."""

class FdpModelResource(ModelResource):
    """Customized django-import-export ModelResource
    """
    external_id = ExternalIdField()

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


class PersonAliasesField(fields.Field):

    def after_import_row(self, resource_class, row, row_result, row_number, **kwargs):
        person_aliases = row.get('person_aliases', None)
        if row_result.import_type == row_result.IMPORT_TYPE_NEW:
            person = Person.objects.get(pk=row_result.object_id)
            if person_aliases:
                for person_alias_value in person_aliases.split(','):
                    person_alias_value = person_alias_value.strip()
                    PersonAlias.objects.create(person=person, name=person_alias_value)
        if row_result.import_type == row_result.IMPORT_TYPE_SKIP or \
                row_result.import_type == row_result.IMPORT_TYPE_UPDATE:  # when only aliases are different
            person = Person.objects.get(pk=row['id'])
            if person_aliases:
                for person_alias_value in person_aliases.split(','):
                    person_alias_value = person_alias_value.strip()
                    try:
                        PersonAlias.objects.get(person=person, name=person_alias_value)
                    except PersonAlias.DoesNotExist:
                        PersonAlias.objects.create(person=person, name=person_alias_value)

    def get_help_html(self):
        return """Use this column to add <code>PersonAlias</code> records to a Person record while importing it. Write 
        the names in comma delimited format. E.g "The shadow, Rocky, Mickey Mouse"."""


resource_model_mapping['Person'].fields['person_aliases'] = PersonAliasesField()


class GroupingAliasesField(fields.Field):

    def after_import_row(self, resource_class, row, row_result, row_number, **kwargs):
        grouping_aliases = row.get('grouping_aliases', None)
        if row_result.import_type == row_result.IMPORT_TYPE_NEW:
            grouping = Grouping.objects.get(pk=row_result.object_id)
            if grouping_aliases:
                for grouping_alias_value in grouping_aliases.split(','):
                    grouping_alias_value = grouping_alias_value.strip()
                    GroupingAlias.objects.create(grouping=grouping, name=grouping_alias_value)
        if row_result.import_type == row_result.IMPORT_TYPE_SKIP or \
                row_result.import_type == row_result.IMPORT_TYPE_UPDATE:  # when only aliases are different
            grouping = Grouping.objects.get(pk=row['id'])
            if grouping_aliases:
                for grouping_alias_value in grouping_aliases.split(','):
                    grouping_alias_value = grouping_alias_value.strip()
                    try:
                        GroupingAlias.objects.get(grouping=grouping, name=grouping_alias_value)
                    except GroupingAlias.DoesNotExist:
                        GroupingAlias.objects.create(grouping=grouping, name=grouping_alias_value)

    def get_help_html(self):
        return """Use this column to add <code>GroupingAlias</code> records to a Grouping record while importing it. 
        Write the names in comma delimited format. E.g "DCA, 4DS, AKF"."""

class GroupingRelationshipField(fields.Field):

    def after_import_row(self, resource_class, row, row_result, row_number, **kwargs):
        if row_result.import_type == row_result.IMPORT_TYPE_NEW:
            grouping = Grouping.objects.get(pk=row_result.object_id)
            for field_name in row.keys():
                # Does it look like this: 'grouping_relationships__exists-in'?
                if re.match(r'grouping_relationships__[a-z\-]+$', field_name):
                    relationship_type_name = field_name.replace('grouping_relationships__', '').replace('-', ' ')
                    type_ = GroupingRelationshipType.objects.get(name__iexact=relationship_type_name)
                    for relationship_pk in row[field_name].split(','):
                        relationship_pk = relationship_pk.strip()
                        GroupingRelationship.objects.create(
                            subject_grouping=grouping,
                            object_grouping=Grouping.objects.get(pk=relationship_pk),
                            type=type_
                        )
                # Does it look like this: 'grouping_relationships__external_id__exists-in'?
                if re.match(r'grouping_relationships__external_id__[a-z\-]+$', field_name):
                    relationship_type_name = field_name.replace('grouping_relationships__external_id__', '') \
                        .replace('-', ' ')
                    type_ = GroupingRelationshipType.objects.get(name__iexact=relationship_type_name)
                    for relationship_external_id in row[field_name].split(','):
                        relationship_external_id = relationship_external_id.strip()
                        if relationship_external_id:
                            bulk_import = BulkImport.objects.get(
                                table_imported_to=Grouping.get_db_table(),
                                pk_imported_from=relationship_external_id
                            )
                            GroupingRelationship.objects.create(
                                subject_grouping=grouping,
                                object_grouping=Grouping.objects.get(pk=bulk_import.pk_imported_to),
                                type=type_
                            )

    def get_help_html(self):
        return f"""To related a group to another group while importing it, use the grouping_relationships column. 
        Uses a special column name syntax: 
        <code>grouping_relationships__[relationship name]</code> or <code>grouping_relationships__external_id__[
        relationship name]</code>. Where [relationship name] is an existing GroupingRelationship set in all lower 
        case with spaces replaced with hyphens.<br>Examples: <code>grouping_relationships__reports-to</code> or 
        <code>grouping_relationships__external_id__reports-to</code>. The form without <code>__external_id</code> 
        expects PKs, the form with <code>__external_id</code> expects external IDs.
        """

    def get_available_extensions(self):
        return ['__[a-z\-]+$','__external_id__[a-z\-]+$']


resource_model_mapping['Grouping'].fields['grouping_aliases'] = GroupingAliasesField()
resource_model_mapping['Grouping'].fields['grouping_relationships'] = GroupingRelationshipField()


def is_law_enforcement_required_before_import_row(resource_class, row, row_number, **kwargs):
    # Make "is_law_enforcement" required
    if 'is_law_enforcement' not in row:
        raise Exception('"is_law_enforcement" is missing but required')


setattr(resource_model_mapping['Grouping'].fields['is_law_enforcement'], 'before_import_row',
    is_law_enforcement_required_before_import_row)

setattr(resource_model_mapping['Person'].fields['is_law_enforcement'], 'before_import_row',
    is_law_enforcement_required_before_import_row)

# Before import
#
#
# On import, locate relationship columns in external id form, and resolve the respective pk
# Modify the before_import_row hook with our custom transformations
def before_import_row(resource_class, row, row_number=None, **kwargs):
    for _, field in resource_class.fields.items():
        try:
            field.before_import_row(resource_class, row, row_number, **kwargs)
        except AttributeError:
            pass



# After import
#
#
def after_import_row(resource_class, row, row_result, row_number=None, **kwargs):
    for _, field in resource_class.fields.items():
        try:
            field.after_import_row(resource_class, row, row_result, row_number, **kwargs)
        except AttributeError:
            pass


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
        'Grouping': ['counties', ],
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
        return f"""Accepts <code>{ self.model.__name__ }</code> { self.field }s rather than 
        PKs by default. Accepts external ids using the <code>__external_id</code> extension.
        """

    def get_available_extensions(self):
        return ['__external_id']


def external_id_get_available_extensions(self):
    return ['__external_id']


def foreign_key_widget_help_html(self):
    if self.field == 'pk':
        return f"""References <a href="#mapping-{ self.model.__name__ }"><code>{self.model.__name__}</code></a> by PK.
        Accepts external ids using <code>__external_id</code> extension.
        """
    elif self.field == 'name':
        return f"""Accepts <a href="#mapping-{ self.model.__name__ }"><code>{ self.model.__name__ }</code></a>
        { self.field }s rather than PKs by default. Accepts external ids using the <code>__external_id</code> extension.
        """


import_export.widgets.ForeignKeyWidget.get_help_html = foreign_key_widget_help_html
import_export.widgets.ForeignKeyWidget.get_available_extensions = external_id_get_available_extensions


def many_to_many_widget_help_html(self):
    if self.field == 'pk':
        return f"""References <a href="#mapping-{ self.model.__name__ }"><code>{self.model.__name__}</code></a> by PK. 
        Accepts external ids using the <code>__external_id</code> extension.
        """
    elif self.field == 'name':
        return f"""Accepts <a href="#mapping-{ self.model.__name__ }"><code>{ self.model.__name__ }</code></a>
        { self.field }s rather than PKs by default. Accepts external ids using the <code>__external_id</code> extension.
        """


import_export.widgets.ManyToManyWidget.get_help_html = many_to_many_widget_help_html
import_export.widgets.ManyToManyWidget.get_available_extensions = external_id_get_available_extensions

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


# Populate the resource mapping fields with details for printing on the importer mapping documentation page
for model_name, mapping in resource_model_mapping.items():
    django_model_class = get_data_model_from_name(model_name)
    for field_name, field in mapping.fields.items():
        try:
            django_field = getattr(django_model_class, field_name).field
            django_field_type_name = type(django_field).__name__
            setattr(field, 'django_field_type_name', django_field_type_name)
            setattr(field, 'django_field_help_text', django_field.help_text)
        except AttributeError:
            # Skip non-django fields like `external_id`
            pass

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

    def validate_field_names_mapping(resource, input_sheet):
        """Do all of the fields in the import sheet line up with fields for the resource? If any don't match,
        flag them to warn the user. TODO: If any are missing that are required flag them."""
        error_messages = []

        valid_field_names = []
        for field_name, field_object in resource.fields.items():
            valid_field_names.append(field_name)
            try:
                extensions = field_object.get_available_extensions()
                for extension in extensions:
                    valid_field_names.append(field_name + extension)
            except AttributeError:
                pass
        for input_field in input_sheet.headers:
            if input_field not in valid_field_names:
                error_messages.append(f"WARNING: {input_field} not a valid column name for"
                      f" {resource_class.Meta.model.__name__} imports")

        return error_messages

    error_messages = validate_field_names_mapping(resource, input_sheet)
    if len(error_messages) > 0:
        batch_record.general_errors = '\n'.join(error_messages)
        batch_record.errors_encountered = True
        batch_record.save()

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
