import tablib
from import_export import resources, widgets
from import_export.resources import ModelResource

from core.models import Person


class FdpModelResource(ModelResource):
    pass


class BooleanWidgetValidated(widgets.BooleanWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value in self.NULL_VALUES:
            return None
        elif value in self.TRUE_VALUES:
            return True
        elif value in self.FALSE_VALUES:
            return False
        else:
            raise ValueError("Enter a valid boolean value.")


FdpModelResource.WIDGETS_MAP['BooleanField'] = \
    BooleanWidgetValidated

PersonResource = resources. \
    modelresource_factory(
        model=Person, resource_class=FdpModelResource)
