from django.db import models


class ImportBatch(models.Model):
    start_time = models.DateTimeField(auto_now=True)
    target_model_name = models.CharField(max_length=256)
    number_of_rows = models.IntegerField()
    errors_encountered = models.BooleanField()
    submitted_file_name = models.CharField(max_length=1024)

    def __str__(self):
        # number, import time, filename, model, number of records,
        # and whether it succeeded or not.
        return f"{self.pk} | {self.start_time:%Y-%m-%d %H:%M:%S} | {self.submitted_file_name} | " \
               f"{self.target_model_name} | {self.number_of_rows} | "\
               f"{'Errors encountered' if self.errors_encountered else 'No errors'}"


class ImportedRow(models.Model):
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='imported_rows')
    row_number = models.IntegerField()
    action = models.CharField(max_length=128, null=True)
    errors = models.TextField(null=True)
    info = models.TextField(null=True)
    imported_record_pk = models.CharField(max_length=128, null=True)
    imported_record_name = models.CharField(max_length=1024, null=True)

    def __str__(self):
        return f"{self.row_number} | {self.action} | {self.errors} | {self.info} | {self.imported_record_name} | {self.imported_record_pk}"


class ErrorRow(models.Model):
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='error_rows')
    row_number = models.IntegerField()
    error_message = models.TextField()
    row_data = models.TextField()

    def __str__(self):
        return f"{self.row_number} | {self.error_message} | {self.row_data}"
