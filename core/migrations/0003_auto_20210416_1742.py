# Generated by Django 3.1.3 on 2021-04-16 17:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_auto_20210211_0825'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='grouping',
            unique_together={('name', 'address')},
        ),
        migrations.RemoveField(
            model_name='grouping',
            name='code',
        ),
    ]

