from django import template
from django.template import Template, Context

from core.models import Person

register = template.Library()


@register.filter
def teaser_person(person: Person) -> str:
    # PREPROCESSING
    # Aliases
    aliases = [alias.name for alias in person.person_aliases.all()]
    # Identifiers
    identifiers = [identifier.identifier for identifier in person.person_identifiers.all()]
    # Commands
    groups = [person_grouping.grouping.name for person_grouping in person.person_groupings.all()]

    context = Context({
        'profile_url': person.get_profile_url,
        'name': person.name,
        'aliases': aliases,
        'identifiers': identifiers,
        'groups': groups,
    })

    # TEMPLATING
    template_ = Template("""<a href="{{profile_url}}">{{name}}</a> 
    {% if aliases %}({{ aliases|join:', ' }}){% endif %}
    {% if identifiers %} &ndash; {{ identifiers|join:', ' }}{% endif %}
    {% if groups %} &ndash; {{ groups|join:', ' }}{% endif %}
    """)

    return template_.render(context)


@register.filter
def person_search_ranking_debug(person: Person) -> str:
    template_ = Template("""
    <p>
    name: {{ person.search_tgs_name }}
    identifiers: {{ search_tgs_identifiers }}
    aliases: {{ search_tgs_aliases }}
    </p>
    """)

    return template_.render(Context({'person': person}))
