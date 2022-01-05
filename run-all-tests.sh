#!/usr/bin/env bash

if command -v xvfb-run &> /dev/null
then
  xvfb-run -a -e /dev/stdout python manage.py test -v 2 --settings=fdp.configuration.test.test_local_settings
  xvfb-run -a -e /dev/stdout python manage.py test -v 2 --settings=fdp.configuration.test.test_azure_settings
  xvfb-run -a -e /dev/stdout python manage.py test -v 2 --settings=fdp.configuration.test.test_azure_only_settings
else
  echo "WARNING: xvfb-run couldn't be found. SKIPPING Selenium tests..."
  python manage.py test -v 2 --settings=fdp.configuration.test.test_local_settings
  python manage.py test -v 2 --settings=fdp.configuration.test.test_azure_settings
  python manage.py test -v 2 --settings=fdp.configuration.test.test_azure_only_settings
fi
