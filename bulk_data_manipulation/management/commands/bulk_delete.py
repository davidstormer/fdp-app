from django.core.management.base import BaseCommand
from bulk_data_manipulation.common import get_record_from_external_id, ImportErrors, ExternalIdMissing, RecordMissing
from importlib import import_module
from bulk.models import BulkImport
from django.db import transaction
import os

help_text = """Delete imported records based on external ID. Delete either small set given as positional arguments on 
the commandline or take a file full of ids delimited by lines."""


def get_model_from_import_string(import_string: str) -> object:
    """Assumes that import string follows the pattern '[app_name].models.[model_name]'"""
    model_import_elements = import_string.split('.')
    app_name = model_import_elements[0]
    if model_import_elements[1] != 'models':
        raise Exception(f"Model import string must follow the pattern '[app_name].models.[model_name]' but "
                        f"{model_import_elements[1]} != 'models'")
    model_name = model_import_elements[2]
    model = getattr(getattr(import_module(app_name), 'models'), model_name)
    return model


def delete_imported_record(model, external_id, delete_external_id=False):
    try:
        bulk_import_record = BulkImport.objects.get(
          pk_imported_from=external_id,
          table_imported_to=model.get_db_table()
          )
    except BulkImport.DoesNotExist as e:
        raise ExternalIdMissing(f"Can't find external id {external_id} for model {model.get_verbose_name()}")
    pk = bulk_import_record.pk_imported_to
    try:
        record = model.objects.get(pk=pk)
    except model.DoesNotExist as e:
        raise RecordMissing(f"Can't delete! Record does not exist model: {model.get_verbose_name()} pk: {pk} ext_id:"
                            f" {external_id}")
    record.delete()
    if delete_external_id is True:
        bulk_import_record.delete()


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('model', type=str, help="Model class, e.g. 'core.models.Person'")
        parser.add_argument('input_file', type=str)

    def handle(self, *args, **options):
        delete_external_ids = False
        if os.stat(options['input_file']).st_size < 1:
            self.stdout.write(self.style.ERROR(f"WARNING! {options['input_file']} is an empty file. Doing nothing. "
                                               f"Quitting..."))
        model = get_model_from_import_string(options['model'])
        self.stdout.write(self.style.WARNING(
            f"Delete {model} records..."
        ))
        with open(options['input_file'], 'r') as csv_fd:
            try:
                with transaction.atomic():
                    errors = []
                    for external_id in csv_fd:
                        external_id = external_id.strip()
                        try:
                            delete_imported_record(model, external_id, delete_external_id=delete_external_ids)
                        except Exception as e:
                            errors.append(e)

                    if len(errors) > 0:
                        self.stdout.write(self.style.ERROR("Errors encountered! Undoing..."))
                        for error in errors:
                            self.stdout.write(self.style.ERROR(' '.join(error.args)))
                        self.stdout.write(self.style.ERROR("Undoing..."))

                        raise ImportErrors
            except ImportErrors:
                self.stdout.write(self.style.ERROR("Quitting..."))
