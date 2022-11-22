import sys
from .settings import *

# Disable logging to Django log files. This fixes issues with Celery trying to write to Django's log files, causing
# permissions issues on Azure App Service setup, because Gunicorn runs as root on Azure App service, but the Celery
# daemon should NOT run as root, so the Celery daemon shouldn't write to the log file as the main django processes.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    "handlers": {
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
         },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/celery/django.log',  # Owned by celery.celery, see deploy/azure/startup-default.sh
        },
    },
    'root': {
        'handlers': ["console", "file"],
        'level': 'INFO',
    },
}
