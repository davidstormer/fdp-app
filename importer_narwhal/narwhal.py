import tablib
from import_export import resources
from import_export.resources import ModelResource
from import_export.results import Result

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


# We'll need a mapping of FDP data models and their corresponding
# django-import-export resource.
def _compile_resources():
    import_export_resources = {}

    for model_name in MODEL_ALLOW_LIST:
        app_name = ModelHelper.get_app_name(model=model_name)
        model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model_name)

        resource = resources. \
            modelresource_factory(
                model=model_class, resource_class=FdpModelResource)
        import_export_resources[model_name] = resource
    return import_export_resources


resource_model_mapping = _compile_resources()


def do_import(model_name: str, input_file: str):
    """Main api interface with narwhal importer
    """
    with open(input_file, 'r') as fd:
        input_sheet = tablib.Dataset().load(fd)
        resource_class = resource_model_mapping[model_name]
        resource = resource_class()
        result = resource.import_data(input_sheet, dry_run=True)
        if result.has_validation_errors():
            return result
        else:
            result = resource.import_data(input_sheet, dry_run=False)
            return result
