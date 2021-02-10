from django.utils.translation import gettext as _
from django.core.mail import send_mail, mail_admins
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.views import PasswordResetView
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.conf import settings
from inheritable.models import AbstractIpAddressValidator, AbstractConfiguration
from inheritable.views import SecuredSyncTemplateView, SecuredSyncRedirectView
from .models import PasswordReset, FdpUser
from .forms import FdpUserPasswordResetForm, FdpUserPasswordResetWithReCaptchaForm
from django_otp import devices_for_user
from csp.decorators import csp_update, csp_replace


class SettingsTemplateView(SecuredSyncTemplateView):
    """ Page that allows users to change settings related to their account, such as 2FA and passwords.

    """
    template_name = 'settings.html'

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(SettingsTemplateView, self).get_context_data(**kwargs)
        u = self.request.user
        context.update({
            'title': _('Settings'),
            'description': _('Manage settings related to your account.'),
            'email': u.email,
            'name': u.get_full_name(),
            'role': u.role_txt,
            'fdp_organization': u.organization_txt
        })
        return context


class ConfirmPasswordChangeTemplateView(SecuredSyncTemplateView):
    """ Page that allows users to confirm that they wish to change their password.

    """
    template_name = 'confirm_password_change.html'

    def test_func(self):
        """ Ensures that user has a changeable password.

        :return: True if user has a changeable password, false otherwise.
        """
        return super(ConfirmPasswordChangeTemplateView, self).test_func() and self.request.user.has_changeable_password

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(ConfirmPasswordChangeTemplateView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Change Password'),
            'description': _('Confirmation to change the password.')
        })
        return context

    def dispatch(self, request, *args, **kwargs):
        """ Ensures that required settings are specified for a password change email.

        :param request: Http request object.
        :param args:
        :param kwargs:
        :return:
        """
        if not AbstractConfiguration.can_do_password_reset():
            raise ImproperlyConfigured('Password reset is not supported with this configuration')
        return super(ConfirmPasswordChangeTemplateView, self).dispatch(request=request, *args, **kwargs)


class ConfirmTwoFactorResetTemplateView(SecuredSyncTemplateView):
    """ Page that allows users to confirm that they wish to reset their 2FA.

    """
    template_name = 'confirm_2fa_reset.html'

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(ConfirmTwoFactorResetTemplateView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Reset 2FA'),
            'description': _('Confirmation to reset two factor authentication.')
        })
        return context


class ResetPasswordRedirectView(SecuredSyncRedirectView):
    """ Trip to server, redirecting to the login page, resetting the user's password.

    """
    pattern_name = 'password_reset_done'

    def test_func(self):
        """ Ensures that user has a changeable password.

        :return: True if user has a changeable password, false otherwise.
        """
        return super(ResetPasswordRedirectView, self).test_func() and self.request.user.has_changeable_password

    def dispatch(self, request, *args, **kwargs):
        """ Invalidate user's current password, log out user, record password reset and send
        email.

        :param request: Http request object.
        :param args:
        :param kwargs:
        :return:
        """
        if not AbstractConfiguration.can_do_password_reset():
            raise ImproperlyConfigured('Password reset is not supported with this configuration')
        user = request.user
        ip_address = AbstractIpAddressValidator.get_ip_address(request=request)
        # limit hasn't been reached for user or IP address to reset password
        if PasswordReset.can_reset_password(user=user, ip_address=ip_address, email=None):
            response = super(ResetPasswordRedirectView, self).dispatch(request, *args, **kwargs)
            # Create password reset form
            form = FdpUserPasswordResetForm({'email': user.email})
            if form.is_valid():
                # Invalidate current password
                PasswordReset.invalidate_password_logout(user=user, request=request)
                # Send the password reset link
                form.save(request=request)
            # something is wrong with the form's configuration
            else:
                raise Exception('FDPUserPasswordResetForm was not valid')
        # limit has been reached for password resets
        else:
            raise Exception('Password reset rate limits have been reached')
        return response


class FdpPasswordResetView(PasswordResetView):
    """ Overrides the PasswordResetView to ensure that rate limit is checked before a password reset, and that the
    password reset is logged.

    """
    # Form extended so that password reset is logged and recaptcha is used
    form_class = FdpUserPasswordResetWithReCaptchaForm

    @method_decorator(csrf_protect)
    @csp_update(FRAME_SRC='https://www.google.com/recaptcha/', DEFAULT_SRC="'unsafe-inline'")
    @csp_replace(
        SCRIPT_SRC=[
            "'unsafe-inline'",
            "'self'",
            'https://www.google.com/recaptcha/',
            'https://www.gstatic.com/recaptcha/'
        ]
    )
    def dispatch(self, *args, **kwargs):
        """ Invalidate user's current password, log out user, record password reset and send
        email.

        :param args:
        :param kwargs:
        :return:
        """
        if not AbstractConfiguration.can_do_password_reset():
            raise ImproperlyConfigured('Password reset is not supported with this configuration')
        request = self.request
        if request.method == 'POST':
            ip_address = AbstractIpAddressValidator.get_ip_address(request=request)
            email = request.POST.get('email', None)
            # limit hasn't been reached for email or IP address to reset password
            if PasswordReset.can_reset_password(user=None, ip_address=ip_address, email=email):
                user = FdpUser.objects.get(email=email)
                # Invalidate current password
                PasswordReset.invalidate_password_logout(user=user, request=request)
            # limit has been reached for password resets
            else:
                raise Exception('Password reset rate limits have been reached')
        return super(FdpPasswordResetView, self).dispatch(*args, **kwargs)


class ResetTwoFactorRedirectView(SecuredSyncRedirectView):
    """ Trip to server, redirecting to the login page, resetting the user's password and 2FA.

    """
    # If password resets are configured, then view redirects to password_reset_done view.
    # If password resets are not configured, then view redirects to logout view.
    pattern_name = 'password_reset_done' if AbstractConfiguration.can_do_password_reset() else 'logout'

    @staticmethod
    def __remove_all_2fa_devices(user):
        """ Removes all 2FA devices for a user.

        :param user: User for which to remove 2FA devices.
        :return: Nothing.
        """
        for device in devices_for_user(user):
            device.delete()

    @classmethod
    def __dispatch_with_password_reset(cls, request, form):
        """ Performs the 2FA reset with password resets configured.

        :param request: Http request object.
        :param form: Validated password reset form.
        :return: Nothing.
        """
        user = request.user
        # invalidate current password and log user out of their account
        PasswordReset.invalidate_password_logout(user=user, request=request)
        # remove all 2FA devices for user
        cls.__remove_all_2fa_devices(user=user)
        # send the password reset link
        form.save(request=request)
        # notify user that their 2FA has been reset
        send_mail(
            _('FDP 2FA Reset'),
            _('Your Full Disclosure Project (FDP) Two-Factor Authentication (2FA) has been reset. If you did '
              'not initiate this reset, please contact {a}.'.format(a=settings.DEFAULT_FROM_EMAIL)),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        # notify admins that user has reset their 2FA
        mail_admins(
            subject=_('FYI - User resets 2FA'),
            message=_('User {u} has reset their 2FA.'.format(u=user.email))
        )

    @classmethod
    def __dispatch_without_password_reset(cls, request):
        """ Performs the 2FA reset without password resets configured.

        :param request: Http request object.
        :return: Nothing.
        """
        user = request.user
        # log user out of their account
        PasswordReset.logout(request=request)
        # remove all 2FA devices for user
        cls.__remove_all_2fa_devices(user=user)

    def dispatch(self, request, *args, **kwargs):
        """ Remove 2FA devices, invalidate user's current password, log out user and send email.

        :param request: Http request object.
        :param args:
        :param kwargs:
        :return: Redirect response to password reset completed view or logout view.
        """
        user = request.user
        response = super(ResetTwoFactorRedirectView, self).dispatch(request, *args, **kwargs)
        # Create password reset form
        form = FdpUserPasswordResetForm({'email': user.email})
        if form.is_valid():
            if AbstractConfiguration.can_do_password_reset():
                self.__dispatch_with_password_reset(request=request, form=form)
            else:
                self.__dispatch_without_password_reset(request=request)
            return response
        # something is wrong with the form's configuration
        else:
            raise Exception('FDPUserPasswordResetForm was not valid')
