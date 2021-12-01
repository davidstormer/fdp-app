from bulk.models import BulkImport


class ImportErrors(Exception):
    pass


class ExternalIdMissing(Exception):
    pass


class RecordMissing(Exception):
    pass


class ExternalIdDuplicates(Exception):
    pass


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
