import tablib
from import_export import resources, fields
from import_export.resources import ModelResource
from import_export.widgets import ForeignKeyWidget

from bulk_data_manipulation.common import get_record_from_external_id
from importer_narwhal.widgets import BooleanWidgetValidated
from supporting.models import PersonIdentifierType
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
def dereference_external_ids(resource_class, row, row_number=None, **kwargs):
    for model_name in MODEL_ALLOW_LIST:
        # Look for any fields that follow the pattern '[model name]__external' and dereference them to their pks
        try:
            external_id = row[f'{model_name.lower()}__external']
            model_class = get_data_model_from_name(model_name)
            referenced_record = get_record_from_external_id(model_class, external_id)
            row[model_name.lower()] = referenced_record.pk
        except KeyError:
            pass


# Modify the before_import_row hook with our custom transformations
def global_before_import_row(resource_class, row, row_number=None, **kwargs):
    dereference_external_ids(resource_class, row, row_number, **kwargs)


# Amend the resources map with update resources, applying the above customizations
for resource in resource_model_mapping.keys():
    resource_model_mapping[resource].before_import_row = global_before_import_row


# Experiment with natural keys
class PersonIdentifierGetOrCreate(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            try:
                return self.get_queryset(value, row, *args, **kwargs).get(**{self.field: value})
            except:
                return PersonIdentifierType.objects.create(name=value)
        else:
            return None


resource_model_mapping['PersonIdentifier'].fields['person_identifier_type'] = fields.Field(
    column_name='person_identifier_type',
    attribute='person_identifier_type',
    widget=PersonIdentifierGetOrCreate(PersonIdentifierType, 'name')
)


# Define data models for holding the error report data from an import that was run
class ImportReportRow:
    def __init__(self, row_number: int, error_message: str, row_data: str):
        self.row_number = row_number
        self.error_message = error_message
        self.row_data = row_data

    def __repr__(self):
        return f"{self.row_number} | {self.error_message} | {self.row_data}"


class ImportReport:
    def __init__(self):
        self.validation_errors = []
        self.database_errors = []

    def __str__(self):
        return f"""
        validation_errors: {len(self.validation_errors)}
        database_errors: {len(self.database_errors)}
        """


# The business
def do_import(model_name: str, input_file: str):
    """Main api interface with narwhal importer
    """
    with open(input_file, 'r') as fd:
        input_sheet = tablib.Dataset().load(fd)
        resource_class = resource_model_mapping[model_name]
        resource = resource_class()
        result = resource.import_data(input_sheet, dry_run=True)

        import_report = ImportReport()

        if result.has_validation_errors():
            for invalid_row in result.invalid_rows:
                import_report.validation_errors.append(
                    ImportReportRow(invalid_row.number, str(invalid_row.error_dict), str(invalid_row.values))
                )
        else:
            result = resource.import_data(input_sheet, dry_run=False)
            if result.has_errors():
                for error_row in result.row_errors():
                    row_num = error_row[0]
                    errors = error_row[1]
                    for error in errors:
                        import_report.database_errors.append(
                            ImportReportRow(row_num, str(error.error), str(dict(error.row)))
                        )
        return import_report
