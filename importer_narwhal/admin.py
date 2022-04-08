from django.contrib import admin
from importer_narwhal.models import ImportBatch


class ImportBatchAdmin(admin.ModelAdmin):
    pass


admin.site.register(ImportBatch, ImportBatchAdmin)
