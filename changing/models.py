from django.db import models
from django.utils.translation import gettext_lazy as _


class LawEnforcementCategories(models.TextChoices):
    """ Categories used to populate the select element in the "changing" forms' interfaces for the "is_law_enforcement"
    fields on relevant models.

    """
    #: Yes, instance being created or edited is law enforcement.
    YES = 'Y', _('Yes')
    #: No, instance being created or edited is NOT law enforcement.
    NO = 'N', _('No')
    #: Unselected value in interface for instance being created or edited.
    __empty__ = _('Please specify')

    @classmethod
    def convert_to_boolean(cls, select_val):
        """ Converts the select element value that is used in the interface to a boolean value that can be assigned to
        the attribute on the model instance.

        :param select_val: Select element value that can be used in the interface.
        :return: Corresponding boolean value that can be assigned to the attribute on the model instance.
        """
        return select_val == cls.YES.value

    @classmethod
    def convert_to_select_val(cls, boolean_val):
        """ Converts the boolean value defined on the attribute on the model instance to the select element value
        that can be used in the interface.

        :param boolean_val: Boolean value defined on the attribute on the model instance.
        :return: Corresponding select element value that can be used in the interface.
        """
        return cls.YES if boolean_val else cls.NO
