from import_export import resources
from import_export.resources import ModelResource
from importer_narwhal.widgets import BooleanWidgetValidated
from wholesale.models import ModelHelper

# The available list of models to import to
# in the interface is based on this.
MODEL_ALLOW_LIST = [
    'Person',
    'Content',
    'PersonRelationship',
    'PersonIdentifier',
]


class FdpModelResource(ModelResource):
    """Customized django-import-export ModelResource
    """
    pass


# Some of the stock widgets don't meet our needs
# Override them with our custom versions
FdpModelResource.WIDGETS_MAP['BooleanField'] = \
    BooleanWidgetValidated


# We'll need a mother list of models and their corresponding
# django-import-export resource.
def compile_resources():
    import_export_resources = {}

    for model_name in MODEL_ALLOW_LIST:
        app_name = ModelHelper.get_app_name(model=model_name)
        model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model_name)

        resource = resources. \
            modelresource_factory(
                model=model_class, resource_class=FdpModelResource)
        import_export_resources[model_name] = resource
    return import_export_resources


resource_model_mapping = compile_resources()
