# Generated by Django 3.1.14 on 2022-07-22 14:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_auto_20220721_1920'),
    ]

    operations = [
        migrations.RenameField(
            model_name='grouping',
            old_name='is_inactive',
            new_name='ended_unknown_date',
        ),
        migrations.RenameField(
            model_name='persongrouping',
            old_name='is_inactive',
            new_name='ended_unknown_date',
        ),
    ]
