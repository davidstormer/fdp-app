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
        raise ExternalIdMissing(f"Can't find external id {external_id} for model {model.get_verbose_name()}")
    except BulkImport.MultipleObjectsReturned as e:
        raise ExternalIdDuplicates(f"Multiple external ids found! for {external_id} for model "
                                   f"{model.get_verbose_name()}")

    pk = bulk_import_record.pk_imported_to

    try:
        record = model.objects.get(pk=pk)
    except model.DoesNotExist as e:
        raise RecordMissing(f"Can't find record, does not exist! model: {model.get_verbose_name()} pk: {pk} ext_id:"
                            f" {external_id}")

    return record
