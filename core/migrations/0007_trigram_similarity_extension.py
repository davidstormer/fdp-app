from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_auto_20220128_2000'),
    ]

    operations = [
        TrigramExtension(),
    ]
