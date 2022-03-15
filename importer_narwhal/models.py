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
