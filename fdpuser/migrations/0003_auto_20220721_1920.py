# Generated by Django 3.1.14 on 2022-07-21 19:20

from django.db import migrations, models
import inheritable.models


class Migration(migrations.Migration):

    dependencies = [
        ('fdpuser', '0002_auto_20210921_2132'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eula',
            name='file',
            field=models.FileField(help_text='End-user license agreement file. Should be less than 100MB.<br>Allowed file formats: Adobe PDF .pdf, Microsoft Word 97-2003 .doc, Microsoft Word 2007+ .docx, Text file .txt, Rich-text format .rtf', max_length=254, unique=True, upload_to='eula/%Y/%m/%d/%H/%M/%S/', validators=[inheritable.models.AbstractFileValidator.validate_eula_file_size, inheritable.models.AbstractFileValidator.validate_eula_file_extension], verbose_name='File'),
        ),
    ]
