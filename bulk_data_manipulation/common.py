import os
from importlib import import_module
from csv import DictReader
from django.core.management.base import BaseCommand
from django.db import transaction

from bulk.models import BulkImport
from uuid import uuid4

class ImportErrors(Exception):
    pass


class ExternalIdMissing(Exception):
    pass


class RecordMissing(Exception):
    pass


class ExternalIdDuplicates(Exception):
    pass


def import_record_with_extid(model: object, data: dict, external_id: str = '') -> tuple:
    """Add a record to the system, the way that the bulk importer does by adding a BulkImport record with an external
    id value.
    Returns a dictionary containing the 'record' and 'external_id'.
    """
    if not external_id:
        external_id = str(uuid4())
    record = model.objects.create(**data)
    BulkImport.objects.create(
        table_imported_to=model.get_db_table(),
        pk_imported_to=record.pk,
        pk_imported_from=external_id,
        data_imported='{}'  # make constraints happy...
    )
    return record, external_id


def get_record_from_external_id(model, external_id):
    try:
        bulk_import_record = BulkImport.objects.get(
          pk_imported_from=external_id,
          table_imported_to=model.get_db_table()
          )
    except BulkImport.DoesNotExist as e:
        raise ExternalIdMissing(f"Can't find external id {external_id} for model {model}")
    except BulkImport.MultipleObjectsReturned as e:
        raise ExternalIdDuplicates(f"Multiple external ids found! for {external_id} for model "
                                   f"{model}")

    pk = bulk_import_record.pk_imported_to

    try:
        record = model.objects.get(pk=pk)
    except model.DoesNotExist as e:
        raise RecordMissing(f"Can't find record, does not exist! model: {model} pk: {pk} ext_id:"
                            f" {external_id}")

    return record


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


class CsvBulkCommand(BaseCommand):
    """Customized BaseCommand for including additional helper methods shared by FDP management command tools.
    Further reading: https://docs.djangoproject.com/en/3.2/howto/custom-management-commands/
    """

    def handle(self, *args, **options):
        raise NotImplementedError('subclasses of CsvBulkCommand must provide a handle() method. See '
                                  'https://docs.djangoproject.com/en/3.2/howto/custom-management-commands/')

    def csv_bulk_action(self, options, callback_func, **kwargs):
        if os.stat(options['input_file']).st_size < 1:
            self.stdout.write(self.style.ERROR(f"WARNING! {options['input_file']} is an empty file. Doing nothing. "
                                               f"Quitting..."))
        model = get_model_from_import_string(options['model'])
        self.stdout.write(self.style.WARNING(
            f"Updating {model} records..."
        ))
        with open(options['input_file'], 'r') as csv_fd:
            csv_reader = DictReader(csv_fd)
            try:
                with transaction.atomic():
                    errors = []
                    for row in csv_reader:
                        try:
                            callback_func(model, row, **kwargs)
                        except Exception as e:
                            if options.get('force'):
                                self.stdout.write(self.style.WARNING(
                                    f"{e}"
                                ))
                            else:
                                errors.append({'row_num': csv_reader.line_num, 'message': e})

                    if len(errors) > 0:
                        self.stdout.write(self.style.ERROR("Errors encountered! Undoing..."))
                        for error in errors:
                            self.stdout.write(self.style.ERROR(f"Row {error['row_num']}:"
                                                               f" {' '.join(error['message'].args)}" ))
                        self.stdout.write(self.style.ERROR("Undoing..."))

                        raise ImportErrors
            except ImportErrors:
                self.stdout.write(self.style.ERROR("Quitting..."))


class NoNaturalBooleanValueFound(Exception):
    pass


def parse_natural_boolean_string(value: str or bool or None) -> bool or None:
    """Interpret various spreadsheet indications of 'True' and 'False'.
    Balks if a clear interpretation can't be made.
    Quietly interprets a blank value '' as empty and returns None.
    """
    if value is None:
        return None
    if value is False:
        return False
    if value is True:
        return True

    value = value.lower()
    if value == 'true' or \
            value == 'checked' or \
            value == '1':
        return True
    elif value == 'false' or \
            value == 'unchecked' or \
            value == '0':
        return False
    elif value == '' or \
            value == 'null' or \
            value == 'none':
        return None
    else:
        raise NoNaturalBooleanValueFound
