import factory
from core import models as core_models
from sourcing import models as sourcing_models


class PersonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = core_models.Person

    name = factory.Faker('name')
    is_law_enforcement = True


class GroupingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = core_models.Grouping

    name = factory.Faker('city')
    is_law_enforcement = True


class ContentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = sourcing_models.Content

    name = factory.Faker("sentence")


class IncidentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = sourcing_models.Incident

    description = factory.Faker("paragraph")


factories = {
    'Person': PersonFactory,
    'Grouping': GroupingFactory,
    'Content': ContentFactory,
    'Incident': IncidentFactory,
}
