#!/usr/bin/env bash

if command -v xvfb-run &> /dev/null
then
  xvfb-run -a -e /dev/stdout python manage.py test --parallel -v 2 --settings=fdp.configuration.test.test_local_settings || exit
  xvfb-run -a -e /dev/stdout python manage.py test --parallel -v 2 --pattern=azure_test* --settings=fdp.configuration.test.test_azure_settings || exit
  xvfb-run -a -e /dev/stdout python manage.py test --parallel -v 2 --pattern=azure_only_test* --settings=fdp.configuration.test.test_azure_only_settings || exit
else
  echo "WARNING: xvfb-run couldn't be found. SKIPPING Selenium tests..."
  python manage.py test --parallel -v 2 --settings=fdp.configuration.test.test_local_settings || exit
  python manage.py test --parallel -v 2 --pattern=azure_test* --settings=fdp.configuration.test.test_azure_settings || exit
  python manage.py test --parallel -v 2 --pattern=azure_only_test* --settings=fdp.configuration.test.test_azure_only_settings || exit
fi
