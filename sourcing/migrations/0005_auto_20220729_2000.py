# Generated by Django 3.1.14 on 2022-07-29 20:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sourcing', '0004_auto_20220721_1920'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentcase',
            name='at_least_since',
            field=models.BooleanField(default=False, help_text='Select if start date is the earliest known start date, but not necessarily the true start date'),
        ),
        migrations.AddField(
            model_name='contentcase',
            name='ended_unknown_date',
            field=models.BooleanField(default=False, help_text="Select if you know that it has ceased but you don't know when.", verbose_name='ended at unknown date'),
        ),
    ]
