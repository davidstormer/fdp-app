from celery import Celery
from time import sleep

celery_app = Celery('tasks', broker='redis://', backend='redis://')
# celery_app.config_from_object('celeryconfig')


@celery_app.task
def do_a_think():
    print("one")
    sleep(300)
    print("two")
