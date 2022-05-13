from django import template
from django.template import Template, Context
from django.template.loader import render_to_string

from core.models import Person

register = template.Library()


@register.filter
def teaser_person(person: Person) -> str:
    # PREPROCESSING
    # Aliases
    aliases = [alias.name for alias in person.person_aliases.all()]
    # Identifiers
    identifiers = [identifier for identifier in person.person_identifiers.all()]
    # Ranks
    current_titles = [title.title.name for title in person.person_titles.filter(end_year=0, end_month=0, end_day=0)]
    # Commands
    groups = [person_grouping.grouping.name for person_grouping in person.person_groupings.filter(
        grouping__is_law_enforcement=True)]

    context = {
        'profile_url': person.get_profile_url,
        'name': person.name,
        'aliases': aliases,
        'identifiers': identifiers,
        'current_titles': current_titles,
        'groups': groups,
    }

    return render_to_string('teaser_officer.html', context=context)

@register.filter
def person_search_ranking_debug(person: Person) -> str:
    template_ = Template("""
    <p>
    rank: {{ person.search_rank }}
    name: {{ person.search_name_rank }}
    full text: {{ person.search_full_text_rank }}
    <br>
    {{ person.search_full_text }}
    </p>
    """)

    return template_.render(Context({'person': person}))
