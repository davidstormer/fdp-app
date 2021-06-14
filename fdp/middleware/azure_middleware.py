from functools import partial as functools_partial
from django_otp.middleware import OTPMiddleware, is_verified as otp_is_verified
from django.contrib.auth import get_user_model
from inheritable.models import AbstractConfiguration


def is_verified(user):
    """ Method that is added to every user, to check if user is verified through 2FA enforced through Django.

    Allows users authenticated through Azure Active Directory to use the 2FA implemented through Azure, and so to skip
    the 2FA implemented through Django.

    2FA is implemented in Django through the Django Two-Factor Authentication package.

    See: https://django-two-factor-auth.readthedocs.io/en/stable/

    :return: True if user is verified through the required 2FA, false otherwise.
    """
    # if configured to skip 2FA for Azure Active Directory users (i.e. 2FA is handled through Azure)
    if AbstractConfiguration.skip_django_2fa_for_azure():
        return True
    # otherwise use default is_verified(...) method from Django Two-Factor Authentication package
    else:
        return otp_is_verified(user=user)


class AzureOTPMiddleware(OTPMiddleware):
    """ Extends the middleware implemented by the Django Two-Factor Authentication package, and allows users who are
    authenticated through Azure Active Directory to use the 2FA implemented through Azure, and so to skip the 2FA
    implemented through Django.

    See: https://django-two-factor-auth.readthedocs.io/en/stable/

    """
    def _verify_user(self, request, user):
        """ Sets the is_verified(...) method and any corresponding properties that are relevant for 2FA verification.

        If the system is configured to allow users authenticated through Azure Active Directory to skip the Django
        implemented 2FA verification step, and the particular user for which this method is called is authenticated
        through Azure Active Directory, then the method will use the custom is_verified(...) method that is defined
        above.

        :param request: Http request object.
        :param user: User for which to set 2FA verification method and properties.
        :return: User with the relevant 2FA verification method and properties set.
        """
        user = super(AzureOTPMiddleware, self)._verify_user(request=request, user=user)
        # if configured to skip 2FA for Azure Active Directory users
        if AbstractConfiguration.skip_django_2fa_for_azure():
            # retrieve the user model
            user_model = get_user_model()
            # if this particular user was authenticated through Azure Active Directory
            if user_model.is_user_azure_authenticated(user=user):
                # for this particular user, override the default is_verified(...) method that was set by the middleware
                # defined in the Django Two-Factor Authentication package, and allow the user to skip the Django
                # implemented 2FA verification step
                user.is_verified = functools_partial(is_verified, user)
        return user
