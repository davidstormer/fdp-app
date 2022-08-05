from django.core.management import BaseCommand
from core.models import Person

help_text = f"""Bulk updates search copy fields. Only use this for upgrading an existing system when there's a new version of the search copy field transformations. Otherwise signals on the save() method automatically update search copy fields on every save."""


class Command(BaseCommand):
    help = help_text

    def handle(self, *args, **options):
        [person.reindex_search_fields(commit=True) for person in Person.objects.all()]
