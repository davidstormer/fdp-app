from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import PersonAlias, PersonIdentifier


@receiver(post_save)
def reindex_search_fields_after_updating_foreign_key_models(sender, **kwargs):
    if sender in [PersonAlias, PersonIdentifier]:
        kwargs['instance'].person.reindex_search_fields(commit=True)
