import os

import tablib
from import_export import resources, fields
from import_export.resources import ModelResource
from import_export.widgets import ForeignKeyWidget

from bulk_data_manipulation.common import get_record_from_external_id
from importer_narwhal.models import ImportBatch, ImportedRow
from importer_narwhal.widgets import BooleanWidgetValidated
from wholesale.models import ModelHelper

# The mother list of models to be able to import to.
# The options in the interface are based on this.
MODEL_ALLOW_LIST = [
    'Person',
    'Content',
    'PersonRelationship',
    'PersonIdentifier',
    'PersonAlias',
]


class FdpModelResource(ModelResource):
    """Customized django-import-export ModelResource
    """
    pass


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


# Handle external IDs
#
#
def dereference_external_ids(resource_class, row, row_number=None, **kwargs):
    other_external_id_fields_mapping = {
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
    for field_name in other_external_id_fields_mapping.keys():
        # Look for any fields from the other external id fields above and dereference them to their pks
        try:
            external_id = row[f'{field_name}__external']
            model_class = get_data_model_from_name(other_external_id_fields_mapping[field_name])
            referenced_record = get_record_from_external_id(model_class, external_id)
            row[field_name] = referenced_record.pk
        except KeyError:
            pass


# Modify the before_import_row hook with our custom transformations
def global_before_import_row(resource_class, row, row_number=None, **kwargs):
    dereference_external_ids(resource_class, row, row_number, **kwargs)


# Amend the resources in the map by applying the above customizations
for resource in resource_model_mapping.keys():
    resource_model_mapping[resource].before_import_row = global_before_import_row


# Setup FDP 'type' fields to use custom 'get or create' widget
#
#
get_or_create_foreign_key_fields = \
    {
        'PersonIdentifier': ['person_identifier_type', ],
        'PersonRelationship': ['type', ],
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

# Customize the 'type' fields to use the new ForeignKeyWidgetGetOrCreate widget
# For every supported model
for model_name in resource_model_mapping.keys():
    # Go through each field
    for field_name in resource_model_mapping[model_name].fields.keys():
        # If one of them is on the list of fields to customize...
        for get_or_create_foreign_key_field in get_or_create_foreign_key_fields.get(model_name, []):
            if get_or_create_foreign_key_field == field_name:
                # Customize the field with the ForeignKeyWidgetGetOrCreate widget
                foreign_key_model = get_data_model_from_name(model_name)._meta.get_field(field_name).remote_field.model
                resource_model_mapping[model_name].fields[field_name] = fields.Field(
                    column_name=field_name,
                    attribute=field_name,
                    widget=ForeignKeyWidgetGetOrCreate(
                        foreign_key_model,
                        'name'  # <- Assumes that the 'natural' key is in the 'name' field
                                # may need to be factored into get_or_create_foreign_key_fields
                                # in the future to handle other fields.
                    )
                )


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


# The business
def do_import(model_name: str, input_file: str):
    """Main api interface for narwhal importer
    """

    batch_record = ImportBatch()
    batch_record.target_model_name = model_name
    batch_record.submitted_file_name = os.path.basename(input_file)

    with open(input_file, 'r') as fd:
        input_sheet = tablib.Dataset().load(fd)
        resource_class = resource_model_mapping[model_name]
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
                import_report.validation_errors.append(
                    ErrorReportRow(invalid_row.number, str(invalid_row.error_dict), str(invalid_row.values))
                )
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
                        import_report.database_errors.append(
                            ErrorReportRow(row_num, str(error.error), str(dict(error.row)))
                        )
            else:
                batch_record.errors_encountered = False
                batch_record.save()
                for row_num, row in enumerate(result.rows):
                    ImportedRow.objects.create(
                        row_number=row_num,
                        import_batch=batch_record,
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

        return import_report
