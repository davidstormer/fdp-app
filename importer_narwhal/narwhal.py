import tablib
from import_export import resources, widgets
from import_export.resources import ModelResource

from core.models import Person
from wholesale.models import ModelHelper


class FdpModelResource(ModelResource):
    pass


class BooleanWidgetValidated(widgets.BooleanWidget):
    # Raise an error when no suitable value found.
    # The stock boolean widget doesn't do this!
    # Also support 'checked' for True
    def render(self, value, obj=None):
        if value is None:
            return ""
        return 'TRUE' if value else 'FALSE'

    def clean(self, value, row=None, *args, **kwargs):
        value = value.lower()
        if value in ["", None, "null", "none"]:
            return None
        elif value in ["1", 1, True, "true", 'checked']:
            return True
        elif value in ["0", 0, False, "false"]:
            return False
        else:
            raise ValueError("Enter a valid boolean value.")


# Use our custom boolean widget instead
FdpModelResource.WIDGETS_MAP['BooleanField'] = \
    BooleanWidgetValidated

PersonResource = resources. \
    modelresource_factory(
    model=Person, resource_class=FdpModelResource)

models_to_make_resources_for = [
    'Person',
    'Incident',
]

import_export_resources = {}

for model_name in models_to_make_resources_for:
    app_name = ModelHelper.get_app_name(model=model_name)
    model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model_name)

    resource = resources. \
        modelresource_factory(
            model=model_class, resource_class=FdpModelResource)
    import_export_resources[model_name] = resource
