from celery import Celery, current_task
from time import sleep
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fdp.settings")
django.setup()

from core.models import Person


celery_app = Celery('tasks', broker='redis://', backend='redis://')
# celery_app.config_from_object('celeryconfig')


@celery_app.task
def do_a_think():
    for i in range(10):
        name = f'Celery generated person {i}'
        print(name)
        Person.objects.create(name=name)
        current_task.update_state(
            state='PROGRESS',
            meta={'on_number': i}
        )
        sleep(1)
    print("done")
