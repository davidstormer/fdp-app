from bulk.models import BulkImport
from uuid import uuid4


def import_record_with_extid(model: object, data: dict, external_id: str = '') -> dict:
    """Add a record to the system, the way that the bulk importer does by adding a BulkImport record with an external
    id value.
    Returns a dictionary with keys: record, external_id
    """
    if not external_id:
        external_id = f"external-id-{uuid4()}"
    record = model.objects.create(**data)
    BulkImport.objects.create(
        table_imported_to=model.get_db_table(),
        pk_imported_to=record.pk,
        pk_imported_from=external_id,
        data_imported='{}'  # make constraints happy...
    )
    return {
        'record': record,
        'external_id': external_id
    }
