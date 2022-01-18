# Generated by Django 3.1.13 on 2022-01-18 21:49

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import inheritable.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='WholesaleImport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Automatically added timestamp recording when batch was created.', verbose_name='created timestamp')),
                ('started_timestamp', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp recording when import of data was started.', null=True, verbose_name='started timestamp')),
                ('ended_timestamp', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp recording when import of data was ended.', null=True, verbose_name='ended timestamp')),
                ('action', models.CharField(choices=[('A', 'Add'), ('U', 'Update')], help_text='The nature of the database change that is intended with the import such as add or update.', max_length=1, verbose_name='Action')),
                ('file', models.FileField(help_text='Template file containing data for import. Should be less than 100MB.', max_length=254, unique=True, upload_to='importer/%Y/%m/%d/%H/%M/%S/', validators=[inheritable.models.AbstractFileValidator.validate_wholesale_file_size, inheritable.models.AbstractFileValidator.validate_wholesale_file_extension], verbose_name='File')),
                ('user', models.CharField(help_text='User starting import.', max_length=254, verbose_name='User')),
                ('import_models', models.JSONField(blank=True, help_text='JSON formatted list of model names that were imported through the wholesale import.', null=True, verbose_name='Models')),
                ('import_errors', models.TextField(blank=True, help_text='Errors, if any, that were encountered during the import.', verbose_name='Errors')),
                ('imported_rows', models.PositiveIntegerField(default=0, help_text='Number of rows that were imported.', verbose_name='Rows imported')),
                ('error_rows', models.PositiveIntegerField(default=0, help_text='Number of rows where errors were encountered.', verbose_name='Rows with errors')),
                ('uuid', models.CharField(help_text='Random combination of characters that form a unique identifier for the import. Used to identify corresponding reversion records.', max_length=36, unique=True, validators=[django.core.validators.MinLengthValidator(36)], verbose_name='UUID')),
            ],
            options={
                'verbose_name': 'wholesale import',
                'verbose_name_plural': 'wholesale imports',
                'db_table': 'fdp_wholesale_import',
                'ordering': ['-ended_timestamp', '-started_timestamp'],
            },
        ),
        migrations.CreateModel(
            name='WholesaleImportRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row_num', models.PositiveBigIntegerField(help_text='Row number in template to which this record corresponds.', verbose_name='Row number')),
                ('model_name', models.CharField(help_text='Name of model to which this record corresponds.', max_length=254, verbose_name='Model')),
                ('instance_pk', models.PositiveBigIntegerField(blank=True, help_text='Primary key in database for model instance to which this record was imported.', null=True, verbose_name='Primary key')),
                ('errors', models.TextField(blank=True, default='', help_text='Errors that may have been encountered during the import attempt. Blank if no errors were encountered.', verbose_name='Errors')),
                ('wholesale_import', models.ForeignKey(help_text='Wholesale import to which this record belongs.', on_delete=django.db.models.deletion.CASCADE, related_name='wholesale_import_records', related_query_name='wholesale_import_record', to='wholesale.wholesaleimport', verbose_name='Wholesale import')),
            ],
            options={
                'verbose_name': 'wholesale import record',
                'verbose_name_plural': 'wholesale import records',
                'db_table': 'fdp_wholesale_import_record',
                'ordering': ['-wholesale_import', 'model_name', 'row_num'],
            },
        ),
    ]
