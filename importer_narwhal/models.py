from django.db.models.fields.files import FieldFile
from django.template.defaultfilters import filesizeformat
from django.core.exceptions import ValidationError
from django.db import models
import os

from django.urls import reverse


def validate_import_sheet_extension(file):
    allowed_extensions = ['csv']
    if isinstance(file, FieldFile):
        file = file.name
    extension = os.path.splitext(file)[1][1:].lower()
    if extension not in allowed_extensions:
        raise ValidationError(f'{extension} file not allowed. File must end in one of {allowed_extensions}')


def validate_import_sheet_file_size(file):
    max_file_size = 1e+7  # 10mb
    if file.size > max_file_size:
        raise ValidationError(f'File size {filesizeformat(file.size)} too large. File must be less than {filesizeformat(max_file_size)}.')


# TODO: turn started into created, and add another started that's not auto_now_add
class ImportBatch(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    dry_run_started = models.DateTimeField(null=True, blank=True)
    dry_run_completed = models.DateTimeField(null=True, blank=True)
    started = models.DateTimeField(null=True, blank=True)
    completed = models.DateTimeField(null=True, blank=True)
    target_model_name = models.CharField(max_length=256)
    number_of_rows = models.IntegerField(null=True)
    errors_encountered = models.BooleanField(null=True)
    submitted_file_name = models.CharField(max_length=1024)
    import_sheet = models.FileField(
        upload_to='import-sheets/%Y/%m/%d/%H/%M/%S/',
        validators=[
            validate_import_sheet_extension,
            validate_import_sheet_file_size
        ]
    )

    def get_absolute_url(self):
        return reverse('importer_narwhal:batch', kwargs={'pk': self.pk})

    def __str__(self):
        # number, import time, filename, model, number of records,
        # and whether it succeeded or not.
        return f"{self.pk} | {self.started_fmt} | {self.completed_fmt} | {self.submitted_file_name} | " \
               f"{self.target_model_name} | {self.number_of_rows} | "\
               f"{'Errors encountered' if self.errors_encountered else 'No errors'}"

    @property
    def started_fmt(self):
        if self.started:
            return f"{self.started:%Y-%m-%d %H:%M:%S}"
        else:
            return "Not started yet"

    @property
    def completed_fmt(self):
        if self.started:
            return f"{self.completed:%Y-%m-%d %H:%M:%S}" if self.completed else 'Aborted'
        else:
            return "Not started yet"


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
