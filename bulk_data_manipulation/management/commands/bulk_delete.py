from django.core.management.base import BaseCommand
from bulk_data_manipulation.common import get_record_from_external_id, ImportErrors, ExternalIdMissing, RecordMissing
from importlib import import_module
from bulk.models import BulkImport
from django.db import transaction
from reversion.models import Version
import os

help_text = """Delete imported records based on external ID. Delete either small set given as positional arguments on 
the commandline or take a file full of external ids delimited by lines."""


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
        raise ExternalIdMissing(f"Can't find external id {external_id} for model {model}")
    pk = bulk_import_record.pk_imported_to
    try:
        record = model.objects.get(pk=pk)
    except model.DoesNotExist as e:
        raise RecordMissing(f"Can't delete! Record does not exist model: {model} pk: {pk} ext_id:"
                            f" {external_id}")
    record.delete()
    if delete_external_id is True:
        bulk_import_record.delete()


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('model', type=str, help="Model class, e.g. 'core.models.Person'")
        parser.add_argument('input_file', type=str)
        parser.add_argument('--skip-revisions', default=None, help="Skips records if they have revisions equal to or "
                                                                   "greater than given number e.g. "
                                                                   "'--skip-revisions=1'")
        parser.add_argument('--force', action='store_true', help="Don't undo if records can't be found, ' \
                                                                                         'skip them instead")
        parser.add_argument('--keep-ext-ids', action='store_true', help="Don't delete external ids (BulkImport records)")

    def handle(self, *args, **options):
        if os.stat(options['input_file']).st_size < 1:
            self.stdout.write(self.style.ERROR(f"WARNING! {options['input_file']} is an empty file. Doing nothing. "
                                               f"Quitting..."))
        model = get_model_from_import_string(options['model'])
        self.stdout.write(self.style.WARNING(
            f"Delete {model} records..."
        ))

        skip_list = []
        if options['skip_revisions'] is not None:
            for record in model.objects.all():
                revisions = Version.objects.get_for_object(record)
                if len(revisions) >= int(options['skip_revisions']):
                    try:
                        external_id = BulkImport.objects.get(table_imported_to=model.get_db_table(),
                                                             pk_imported_to=record.pk).pk_imported_from
                        skip_list.append(external_id)
                    except:
                        pass

        with open(options['input_file'], 'r') as csv_fd:
            try:
                with transaction.atomic():
                    errors = []
                    for external_id in csv_fd:
                        external_id = external_id.strip()
                        if external_id not in skip_list:
                            try:
                                delete_imported_record(model, external_id,
                                                       delete_external_id=False if options['keep_ext_ids'] else True)
                                if int(options['verbosity']) > 1:
                                    self.stdout.write(f"Deleted: {model}|{external_id}")
                            except Exception as e:
                                errors.append(e)
                        else:
                            self.stdout.write(self.style.WARNING(f"Skipping {external_id}"))

                    if len(errors) > 0:
                        self.stdout.write(self.style.ERROR("Errors encountered!"))
                        for error in errors:
                            self.stdout.write(self.style.ERROR(' '.join(error.args)))

                        if not options['force']:
                            self.stdout.write(self.style.ERROR("Undoing..."))
                            raise ImportErrors

            except ImportErrors:
                self.stdout.write(self.style.ERROR("Quitting..."))
