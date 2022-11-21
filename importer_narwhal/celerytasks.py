from celery import Celery, current_task
from time import sleep

import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fdp.settings")
django.setup()
# ~~~~~~ Django dependencies below this line ~~~~~~~
from core.models import Person
from importer_narwhal.models import ImportBatch
from importer_narwhal.narwhal import do_dry_run, run_import_batch

celery_app = Celery('tasks', backend='redis://localhost', broker="redis://localhost")
# celery_app.config_from_object('django.conf:settings', namespace='CELERY')


@celery_app.task
def background_do_dry_run(batch_pk: int):
    batch = ImportBatch.objects.get(pk=batch_pk)
    do_dry_run(batch)


@celery_app.task
def background_run_import_batch(batch_pk: int):
    batch = ImportBatch.objects.get(pk=batch_pk)
    run_import_batch(batch)
