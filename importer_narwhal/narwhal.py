import tablib
from import_export import resources, widgets
from import_export.resources import ModelResource

from core.models import Person


class FdpModelResource(ModelResource):
    pass


class BooleanWidgetValidated(widgets.BooleanWidget):
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


FdpModelResource.WIDGETS_MAP['BooleanField'] = \
    BooleanWidgetValidated

PersonResource = resources. \
    modelresource_factory(
        model=Person, resource_class=FdpModelResource)
