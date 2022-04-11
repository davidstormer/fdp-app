from django.core.management.base import BaseCommand
from django.db.models import Model

from bulk_data_manipulation.common import get_record_from_external_id, ImportErrors, ExternalIdMissing, RecordMissing, \
    CsvBulkCommand
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


def delete_imported_record(model, external_id, delete_external_id=False, delete_multiple=False):
    try:
        bulk_import_record = BulkImport.objects.get(
            pk_imported_from=external_id,
            table_imported_to=model.get_db_table()
        )
    except BulkImport.DoesNotExist as e:
        raise ExternalIdMissing(f"Can't find external id {external_id} for model {model}")
    except BulkImport.MultipleObjectsReturned as e:
        if delete_multiple:
            bulk_import_records = BulkImport.objects.filter(
                pk_imported_from=external_id,
                table_imported_to=model.get_db_table()
            )
            # TODO: what if nothing is found?
            things_to_delete = []
            for bulk_import_record in bulk_import_records:
                things_to_delete.append(
                    {
                        'pk': bulk_import_record.pk_imported_to,
                        'bulk_import_instance': bulk_import_record,
                    }
                )
        else:
            raise
        pks_not_found = []
        pks_successfully_deleted = []
        for thing_to_delete in things_to_delete:
            pk = thing_to_delete['pk']
            try:
                record = model.objects.get(pk=pk)
                record.delete()
                pks_successfully_deleted.append(pk)
                if delete_external_id is True:
                    thing_to_delete['bulk_import_instance'].delete()
            except model.DoesNotExist as e:
                pks_not_found.append(thing_to_delete['pk'])
        if pks_not_found:
            raise RecordMissing(
                f"Deleted {model}: {pks_successfully_deleted}. But additional records do not exist model: {model} pk:"
                f" {pks_not_found} ext_id: {external_id}")
    else:
        try:
            model.objects.get(pk=bulk_import_record.pk_imported_to).delete()
            if delete_external_id is True:
                bulk_import_record.delete()
        except model.DoesNotExist as e:
            raise RecordMissing(f"Can't delete! Record does not exist model: {model} pks:"
                                f" {bulk_import_record.pk_imported_to} ext_id: {external_id}")


def delete_imported_record_by_pk(model, pk, external_id=None, delete_external_id=False):
    try:
        record = model.objects.get(pk=pk)
        record.delete()
    except model.DoesNotExist as e:
        raise RecordMissing(f"Can't delete! Record does not exist model: {model} {pk}")
    if delete_external_id:
        try:
            bulk_import_record = BulkImport.objects.get(
                pk_imported_from=external_id,
                table_imported_to=model.get_db_table()
            )
        except BulkImport.DoesNotExist as e:
            raise ExternalIdMissing(f"Can't find external id {external_id} for model {model}")
        bulk_import_record.delete()


class Command(CsvBulkCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('model', type=str, help="Model class, e.g. 'core.models.Person'")
        parser.add_argument('input_file', type=str)
        parser.add_argument('--force', action='store_true',
                            help="Don't undo if records can't be found, skip them instead. When duplicate external "
                                 "ids are found, keep going and delete the associated records.")
        parser.add_argument('--keep-ext-ids', action='store_true',
                            help="Don't delete external ids (BulkImport records)")

    def handle(self, *args, **options):
        if os.stat(options['input_file']).st_size < 1:
            self.stdout.write(self.style.ERROR(f"WARNING! {options['input_file']} is an empty file. Doing nothing. "
                                               f"Quitting..."))
        model = get_model_from_import_string(options['model'])
        self.stdout.write(self.style.WARNING(
            f"Delete {model} records..."
        ))

        def callback_func(model: Model, row: dict) -> None:
            """This function takes a row from the main loop in csv_bulk_action and processes it."""
            external_id = row.get("id__external")
            pk_to_delete = row.get("pk")
            if pk_to_delete:
                pk_to_delete = pk_to_delete.strip()
                if external_id:
                    external_id = external_id.strip()
                    delete_imported_record_by_pk(model, pk_to_delete, external_id=external_id, delete_external_id=True)
                delete_imported_record_by_pk(model, pk_to_delete)
            elif external_id:
                external_id = external_id.strip()
                try:
                    if options['force']:
                        try:
                            delete_imported_record(model, external_id,
                                                   delete_external_id=False if options[
                                                       'keep_ext_ids'] else True,
                                                   delete_multiple=True)
                        except RecordMissing as e:
                            self.stdout.write(self.style.WARNING(
                                f"{e}"
                            ))
                        except ExternalIdMissing as e:
                            self.stdout.write(self.style.WARNING(
                                f"{e}"
                            ))
                    else:
                        delete_imported_record(model, external_id,
                                               delete_external_id=False if options[
                                                   'keep_ext_ids'] else True)
                    if int(options['verbosity']) > 1:
                        self.stdout.write(f"Deleted: {model}|{external_id}")
                except BulkImport.MultipleObjectsReturned as e:
                    bulk_imports = BulkImport.objects.filter(
                        pk_imported_from=external_id,
                        table_imported_to=model.get_db_table()
                    )
                    bulk_import_pks = [bulk_import.pk for bulk_import in bulk_imports]
                    bulk_import_pks.sort()
                    records_pks = []
                    for bulk_import in bulk_imports:
                        records_pks.append(bulk_import.pk_imported_to)
                    records_pks.sort()
                    raise BulkImport.MultipleObjectsReturned(
                        f"Multiple records found for external id {external_id}; BulkImports:"
                        f" {bulk_import_pks}; {model}: {records_pks}")
        self.csv_bulk_action(options, callback_func=callback_func)
