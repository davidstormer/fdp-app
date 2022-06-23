from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20220623_1406'),
    ]

    operations = [
        TrigramExtension(),
    ]
