from django import template
from django.template import Template, Context

from core.models import Person

register = template.Library()


@register.filter
def officer_teaser(officer: Person) -> str:
    template = Template("Hello world {{officer_name}}")
    return template.render(Context({'officer_name': officer.name}))
