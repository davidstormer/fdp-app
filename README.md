# Full Disclosure Project FDP App

This code lives here: https://github.com/nacdl/fdp-app

User documentation lives here: https://fulldisclosure.zendesk.com/

More about the Full Disclosure Project: https://www.nacdl.org/Landing/FullDisclosureProject

# Local development environment installation

These instructions allow you to run the application locally for testing and development. WARNING this is not a setup 
guide for a production environment. Do not use the Vagrant environment for production! It is not secure or robust by 
design.

First download and install Vagrant: https://www.vagrantup.com/

Then:

```shell
# Set up vagrant environment
vagrant up

# Lots of stuff on the screen...

# SSH into vagrant Linux machine terminal
vagrant ssh
```

Then follow the on-screen instructions to start the development web server...

```
FULL DISCLOSURE PROJECT App local development environment
WARNING: Do not use this environment for production!

Add the first user with this command:
'python manage.py createsuperuser  --email admin@localhost'

Then run the testing web server:
'python manage.py runserver 0.0.0.0:8000'

Then point your browser to 'localhost:8000' to see the FDP Application

> To test the Celery background tasks manager on imports and exports run:
> 'sudo service redis-server start'
> 'celery -A importer_narwhal.celerytasks worker -l INFO'
```

small change
small change
