# https://learn.microsoft.com/en-us/azure/developer/python/configure-python-web-app-on-app-service

# Install Redis locally on the app service VM
# "stretch" may need to be updated with newer versions of debian. Use `lsb_release -cs` to get the appropriate value.
curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb stretch main" | tee /etc/apt/sources.list.d/redis.list
apt-get update
apt-get install -y redis

# Start Redis
sleep 1
service redis-server start

# Set up Celery worker pid and logging directories
addgroup --system celery
adduser --system celery
adduser celery celery
mkdir /var/run/celery/
chown celery.celery /var/run/celery
mkdir /var/log/celery/
chown celery.celery /var/log/celery/

# Start Celery worker process
start-stop-daemon --start --oknodo --pidfile /var/run/celery/celery.pid --chuid celery --user celery --group celery
--chdir "$APP_PATH" --startas `which celery` -- multi start worker1 --workdir="$APP_PATH" --app=importer_narwhal.celerytasks --logfile=/var/log/celery/celery.log --pidfile=/var/run/celery/celery.pid --loglevel=INFO

# Run web service
gunicorn --bind=0.0.0.0 --timeout 60 --workers=4 fdp.wsgi
