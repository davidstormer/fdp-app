from import_export import resources
from import_export.fields import Field

from bulk.models import BulkImport
from core.models import Person


class PersonResource(resources.ModelResource):
    external_id = Field()

    class Meta:
        model = Person

    def dehydrate_external_id(self, record):
        try:
            bulk_import_record = \
                BulkImport.objects.get(
                    table_imported_to=record.__class__.get_db_table(),
                    pk_imported_to=record.pk)
            return bulk_import_record.pk_imported_from
        except BulkImport.DoesNotExist:
            return ''


EXPORT_RESOURCES = {
    'Person': PersonResource
}


def do_export(model_name, file_name):
    export_resource = EXPORT_RESOURCES[model_name]
    data_set = export_resource().export()
    with open(file_name, 'w') as fd:
        fd.write(data_set.csv)
