# To setup dependencies

*NOTE: If you use the local development Vagrant skip to "To run tests." Setup steps are unnecessary.* 

Install python requirements:

```shell
pip install -r functional_tests/requirements.txt
```

Selenium setup:

```shell
sudo apt-get update
sudo apt-get install firefox xvfb
cd venv/bin
wget https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz
tar xvzf geckodriver-*-linux64.tar.gz 
```

Latest release of the gecko driver available at: https://github.com/mozilla/geckodriver/releases

More information on setting up selenium: https://selenium-python.readthedocs.io/installation.html#installing-python-bindings-for-selenium

# To run tests

In order for Selenium to launch Firefox you must use the virtual frame buffer (xvfb):

```shell
xvfb-run python manage.py test -v 2 --settings=fdp.configuration.test.test_local_settings functional_tests
```

Note: This runs in a virtual gui frame buffer so you will not actually see the Firefox window. If all tests ran, and 
none were skipped then Firefox/Selenium ran successfully.

# To add more tests
For each new feature add a new test file in this folder using the following format:

```
test_[issue number]_[feature name]
```

Example: `test_FDAB146_social_media_profile_links.py`

Tests for existing features that don't have issue numbers should begin with a stand-in number of zero: 
`test_0_officer_profile_page.py`

Subclass FunctionalTestCase in common.py to leverage some handy tools:

```python3
from functional_tests.common import FunctionalTestCase

class MyTestCase(FunctionalTestCase):
    def test_my_tools(self):
        # Create an account
        # Set the password
        # Set up 2FA tokens
        # Log into the system
        # Get a Django test client
        admin_client = self.log_in(is_administrator=True)
    
        # Parse some html using beautiful soup
        # Find an element using CSS style selectors
        # Get the text contents of the element and its children
        self.get_element_text(
            '<h1 class="my-header"><a href="#">Hello World</a></h1>',
            'h1.my-header')
        # returns: "Hello World"
```
