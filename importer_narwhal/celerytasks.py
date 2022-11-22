from celery import Celery, current_task
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fdp.settings")
django.setup()
# ~~~~~~ Django dependencies below this line ~~~~~~~
from importer_narwhal.models import ImportBatch
from importer_narwhal.narwhal import do_dry_run, run_import_batch

# TODO: FIX THIS SO THAT THE REDIS HOST IS CONFIGURABLE FROM settings.py...
celery_app = Celery('tasks', backend='redis://localhost', broker="redis://localhost")
# celery_app.config_from_object('django.conf:settings', namespace='CELERY')

# # TODO: ADD THIS TO settings_example.py
# Celery
#
# Celery is used for handling background processes.
# By default the Celery broker and results backend is provided by a Redis server running as a daemon on the same
# machine as the web service. If the broker or results backend are located on other servers or using other services
# change them below.
#
# CELERY_BROKER_URL = 'redis://'
# CELERY_BACKEND = 'redis://'
#

# # TODO: ADD THIS TO base_settings.py
#
# Celery
#
#
# Assume that broker and results backend are a locally running Redis server
# These can be overridden by local settings.py for more advanced cloud configurations
# CELERY_BROKER_URL = 'redis://localhost'
# CELERY_BACKEND = 'redis://localhost'
# # Sane defaults for security and stability
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_ACCEPT_CONTENT = ['json']
# CELERY_ENABLE_UTC = True


@celery_app.task
def background_do_dry_run(batch_pk: int):
    batch = ImportBatch.objects.get(pk=batch_pk)
    do_dry_run(batch)


@celery_app.task
def background_run_import_batch(batch_pk: int):
    batch = ImportBatch.objects.get(pk=batch_pk)
    run_import_batch(batch)
