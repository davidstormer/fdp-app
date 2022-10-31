from celery import Celery, current_task
from time import sleep

import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fdp.settings")
django.setup()
# ~~~~~~ Django dependencies below this line ~~~~~~~
from core.models import Person
from importer_narwhal.models import ImportBatch
from importer_narwhal.narwhal import do_dry_run

celery_app = Celery('tasks', backend='redis://localhost', broker="redis://localhost")
# celery_app.config_from_object('django.conf:settings', namespace='CELERY')


@celery_app.task
def do_a_think(num_persons: int):
    # from celery.contrib import rdb
    # rdb.set_trace()
    for i in range(num_persons):
        name = f'Celery generated person {current_task.request.id} {i}'
        print(name)
        Person.objects.create(name=name)
        current_task.update_state(
            state='PROGRESS',
            meta={'on_number': i}
        )
        sleep(1)
    print("done")


@celery_app.task
def background_do_dry_run(batch_pk: int):
    batch = ImportBatch.objects.get(pk=batch_pk)
    do_dry_run(batch)
