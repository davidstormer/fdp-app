# Generated by Django 3.1.14 on 2022-07-21 19:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('verifying', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='verifycontentcase',
            name='description',
            field=models.TextField(blank=True, help_text='', verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='verifyperson',
            name='description',
            field=models.TextField(blank=True, help_text='', verbose_name='Description'),
        ),
    ]
