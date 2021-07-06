from django.contrib.auth import logout
from django.shortcuts import redirect
from fdpuser.models import FdpUser
from importlib.util import find_spec, module_from_spec
# check if social-auth-app-django package is installed
# see: https://python-social-auth-docs.readthedocs.io/en/latest/configuration/django.html
social_core_pipeline_user_spec = find_spec('social_core.pipeline.user')
# social-auth-app-django package is not installed
if not social_core_pipeline_user_spec:
    raise Exception('Please install the package: social-auth-app-django')
# load pipeline.user module in the social-auth-app-django package
social_core_pipeline_user_module = module_from_spec(social_core_pipeline_user_spec)
# initialize pipeline.user module
social_core_pipeline_user_spec.loader.exec_module(social_core_pipeline_user_module)


def create_user(strategy, details, backend, user=None, *args, **kwargs):
    """ Create a user account to correspond to the external authentication, if none was found.

    :param strategy: Current strategy giving access to current store, backend and request.
    :param details: User details given by authentication provider.
    :param backend: Backend in which to create user.
    :param user: Will be none if new user should be created.
    :param args: Ignored.
    :param kwargs: Dictionary containing values to assign to user's fields.
    :return: Dictionary containing new user.
    """
    if user:
        return {'is_new': False}

    fields = dict((name, kwargs.get(name, details.get(name)))
                  for name in backend.setting('USER_FIELDS', social_core_pipeline_user_module.USER_FIELDS))
    if not fields:
        return

    # added to ensure that users authenticated through Azure Active Directory are added as host and
    # only externally authenticable
    fields.update({'is_host': True, 'only_external_auth': True})

    # check if user already exists, since email must be unique
    # tokens may have been removed
    e = {'email': fields['email']}
    return {
        'is_new': True,
        'user': strategy.create_user(**fields) if not FdpUser.objects.filter(**e).exists() else FdpUser.objects.get(**e)
    }


def logout_user(strategy, *args, **kwargs):
    """ Forcibly logs out the user, after their disconnection from Azure Active Directory is complete.

    :param strategy: Current strategy giving access to current store, backend and request.
    :param args: Ignored.
    :param kwargs: Ignored.
    :return: Nothing.
    """
    request = strategy.request
    logout(request)
    return redirect('https://login.microsoftonline.com/common/oauth2/logout')
