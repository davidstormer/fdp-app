from data_wizard import register as data_wizard_register
from .serializers import GroupingAirTableSerializer, PersonAirTableSerializer, IncidentAirTableSerializer, \
    ContentAirTableSerializer, AllegationAirTableSerializer, CountyAirTableSerializer, \
    PersonGroupingAirTableSerializer, PersonTitleAirTableSerializer, PersonPaymentAirTableSerializer, \
    PersonIncidentAirTableSerializer, ContentPersonAirTableSerializer, ContentIdentifierAirTableSerializer, \
    AttachmentAirTableSerializer


# Register models for Django Data Wizard: https://github.com/wq/django-data-wizard
def_prefix = ''
data_wizard_register('{p}Grouping Air Table v1'.format(p=def_prefix), GroupingAirTableSerializer)
data_wizard_register('{p}Person Air Table v1'.format(p=def_prefix), PersonAirTableSerializer)
data_wizard_register('{p}Incident Air Table v1'.format(p=def_prefix), IncidentAirTableSerializer)
data_wizard_register('{p}Content Air Table v1'.format(p=def_prefix), ContentAirTableSerializer)
data_wizard_register('{p}Allegation Air Table v1'.format(p=def_prefix), AllegationAirTableSerializer)
data_wizard_register('{p}County Air Table v1'.format(p=def_prefix), CountyAirTableSerializer)
data_wizard_register('{p}Person-Grouping Air Table v1'.format(p=def_prefix), PersonGroupingAirTableSerializer)
data_wizard_register('{p}Person-Title Air Table v1'.format(p=def_prefix), PersonTitleAirTableSerializer)
data_wizard_register('{p}Person-Payment Air Table v1'.format(p=def_prefix), PersonPaymentAirTableSerializer)
data_wizard_register('{p}Person-Incident Air Table v1'.format(p=def_prefix), PersonIncidentAirTableSerializer)
data_wizard_register('{p}Content-Person Air Table v1'.format(p=def_prefix), ContentPersonAirTableSerializer)
data_wizard_register('{p}Content-Identifier Air Table v1'.format(p=def_prefix), ContentIdentifierAirTableSerializer)
data_wizard_register('{p}Attachment Air Table v1'.format(p=def_prefix), AttachmentAirTableSerializer)
