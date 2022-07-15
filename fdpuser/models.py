from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.sessions.models import Session
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.conf import settings
from django.contrib.auth import logout
from django.core.mail import mail_admins
from django.core.validators import validate_ipv46_address, ValidationError
from inheritable.models import Archivable, AbstractForeignKeyValidator, AbstractIpAddressValidator, \
    AbstractConfiguration, Metable, AbstractFileValidator, AbstractUrlValidator
from datetime import timedelta
from cspreports.models import CSPReport


class FdpCSPReport(CSPReport):
    """ A proxy model for the CSP Report model.

    See: https://github.com/adamalton/django-csp-reports

    """
    class Meta:
        proxy = True
        verbose_name = _('CSP Report')
        verbose_name_plural = _('CSP Reports')


class FdpUserManager(BaseUserManager):
    """ Manager for custom user model defining a FDP user.

    See: https://docs.djangoproject.com/en/2.0/topics/auth/customizing/#substituting-a-custom-user-model

    """
    # serialize manager and make available in migrations
    use_in_migrations = True

    def get_case_insensitive_username_filter_dict(self, username):
        """ Retrieves a dictionary of keyword arguments that can be expanded to filter a queryset of users.

        Return value from method can be expanded, for example, into a queryset's filter(...) or get(...) methods.

        :param username: Username for which to filter the queryset.
        :return: Dictionary of keyword arguments.
        """
        case_insensitive_username_field = '{u}__iexact'.format(u=self.model.USERNAME_FIELD)
        return {case_insensitive_username_field: username}

    def get_by_natural_key(self, username):
        """ Retrieves case insensitive username (email).

        :param username: Username entered by user.
        :return: Case insensitive username.
        """
        filter_dict = self.get_case_insensitive_username_filter_dict(username=username)
        return self.get(**filter_dict)

    def __create_user(self, email, password, **kwargs):
        """ Creates a FDP user.

        :param email: Email address used to uniquely identify the user.
        :param password: Password for user.
        :param kwargs: Dictionary including additional fields and their values used to define user.
        :return: Saved FDP user.
        """
        if not email:
            raise ValueError(_('The email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **kwargs)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **kwargs):
        """ Creates a FDP user.

        :param email: Email address used to uniquely identify the user.
        :param password: Password for user.
        :param kwargs: Dictionary including additional fields and their values used to define user.
        :return: Saved FDP user.
        """
        kwargs.setdefault('is_host', False)
        kwargs.setdefault('is_administrator', False)
        kwargs.setdefault('is_superuser', False)
        return self.__create_user(email, password, **kwargs)

    def create_superuser(self, email, password, **kwargs):
        """ Creates a FDP super user.

        :param email: Email address used to uniquely identify the super user.
        :param password: Password for super user.
        :param kwargs: Dictionary including additional fields and their values used to define user.
        :return: Saved FDP super user.
        """
        kwargs.setdefault('is_host', False)
        kwargs.setdefault('is_administrator', False)
        kwargs.setdefault('is_superuser', True)
        return self.__create_user(email, password, **kwargs)


class FdpOrganization(Archivable):
    """ FDP organizations for users who are not host organization staff members.

    Attributes:
        :name (str): Name of organization using FDP system.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of organization using FDP system'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a FDP organization.

        :return: String representation of a FDP organization.
        """
        return self.name

    @classmethod
    def filter_for_admin(cls, queryset, user):
        """ Filter a queryset for the admin interfaces.

        Assumes that queryset has already been filtered for direct confidentiality, i.e. whether user has access to
        each record based on the record's level of confidentiality. E.g. a confidentiable queryset of Person.

        Can be used to filter for indirect confidentiality, i..e whether user has access to each record based on other
        relevant records' levels of confidentiality. E.g. a queryset of PersonAlias linking to a confidentiality
        queryset of Person.

        :param queryset: Queryset to filter.
        :param user: User for which to filter queryset.
        :return: Filtered queryset.
        """
        return queryset

    class Meta:
        db_table = '{d}fdp_organization'.format(d=settings.DB_PREFIX)
        verbose_name = _('FDP Organization')
        ordering = ['name']


class FdpUser(AbstractUser):
    """ Custom user model defining a FDP user.

    Attributes:
        :email (str): Email address used to uniquely identify the user.
        :is_host (bool): True if user belongs to host organization, false otherwise.
        :is_administrator (bool): True if user is an Administrator, false otherwise.
        :is_superuser (bool): True if user is a Super User, false otherwise.
        :is_active (bool): False if the user is deactivated and cannot log in.
        :only_external_auth (bool): True if user can only be authenticated through an external authentication mechanism
        such as Azure Active Directory, false otherwise.
        :fdp_organization (fk): Organization to which user belongs. Blank is user is a host organization staff member.
        :agreed_to_eula (datetime): Date and time that the user agreed to a EULA. None if user has not agreed to a EULA.

    Properties:
        :is_staff (bool): True if user has access to admin section, false otherwise.
        :role_txt (str): FDP role to which user belongs.
        :organization_txt (str): FDP organization to which user belongs.

    See: https://docs.djangoproject.com/en/2.0/topics/auth/customizing/#substituting-a-custom-user-model

    """
    # User role constants
    GUEST_STAFF_ROLE = _('Guest staff')
    GUEST_ADMIN_ROLE = _('Guest administrator')
    HOST_STAFF_ROLE = _('Host staff')
    HOST_ADMIN_ROLE = _('Host administrator')
    SUP_ROLE = _('Super user')
    NA_ORG = _('Ignored')
    HOST_ORG = _('Host organization')
    #  Remove the following fields
    username = None
    is_staff = None
    date_of_birth = None
    removed_fields = ['username', 'is_staff', 'date_of_birth']
    added_fields = ['is_host', 'is_administrator', 'fdp_organization']

    email = models.EmailField(
        null=False,
        blank=False,
        verbose_name=_('Email address'),
        help_text=_('Email address used as the username to uniquely identify the user'),
        unique=True
    )

    is_host = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name=_('Belongs to host organization'),
        help_text=_('Select if the user belongs to the host organization')
    )

    is_administrator = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name=_('Is Administrator'),
        help_text=_('Select if the user is an Administrator')
    )

    is_superuser = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name=_('Is Super User'),
        help_text=_('Select if the user is a Super User')
    )

    is_active = models.BooleanField(
        null=False,
        blank=False,
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('If not selected, the user is deactivated and cannot log in, regardless of their user role. '
                    'Deactivate users instead of deleting them.')
    )

    only_external_auth = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name=_('Only Externally Authenticated'),
        help_text=_('If selected, the user can only be authenticated through an external authentication mechanism, '
                    'such as Azure Active Directory.')
    )

    fdp_organization = models.ForeignKey(
        FdpOrganization,
        on_delete=models.CASCADE,
        related_name='fdp_users',
        related_query_name='fdp_user',
        blank=True,
        null=True,
        help_text=_('Organization to which user belongs. If user belongs to the host organization, this can be left '
                    'blank.'),
        verbose_name=_('organization')
    )

    agreed_to_eula = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date and time that the user agreed to a EULA. None if user has not agreed to a EULA.'),
        verbose_name=_('EULA agreement')
    )

    @property
    def is_staff(self):
        """ Django provides all staff access to the admin section, so FDP users are staff if they are administrators.

        :return: True if the user has access to the admin section, false otherwise.
        """
        return self.is_administrator or self.is_superuser

    @property
    def role_txt(self):
        """ User-friendly version of role to which current user belongs.

        :return: User-friendly representation of user role.
        """
        if self.is_superuser:
            return self.SUP_ROLE
        else:
            if self.is_host:
                return self.HOST_ADMIN_ROLE if self.is_administrator else self.HOST_STAFF_ROLE
            else:
                return self.GUEST_ADMIN_ROLE if self.is_administrator else self.GUEST_STAFF_ROLE

    @property
    def organization_txt(self):
        """ User-friendly version of FDP organization to which current user belongs.

        :return: User-friendly representation of FDP organization.
        """
        if self.is_superuser:
            return self.NA_ORG
        else:
            '{o}'.format(o=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_organization'))

    @property
    def has_admin_access(self):
        """ Checks whether a user has access to the FDP administrative interface.

        :return: True if user has access, false otherwise.
        """
        return (not self.is_anonymous) and (self.is_superuser or self.is_administrator) and self.is_active

    @property
    def has_changeable_password(self):
        """ Checks whether a user has a password that can be changed or reset.

        :return: True if user has a password that can be changed or reset, false otherwise.
        """
        return self.is_active and not self.only_external_auth

    @property
    def has_import_access(self):
        """ Checks whether a user has access to import files through the Django Data Wizard package.

        Only administrator users belonging to the host organization have access.

        :return: True if user has access, false otherwise.
        """
        return self.has_admin_access and (self.is_host or self.is_superuser)

    def only_user_alter_matching_user(self, obj):
        """ Enforces that users can only change or delete users of matching access levels.

        :param obj: Object to change or delete.
        :return: True if object is changeable or deleteable, false otherwise.
        """
        # Changing a user
        if isinstance(obj, FdpUser):
            # Superuser can change any user
            if self.is_superuser:
                return True
            # Host administrators can change anything but super users
            elif self.is_administrator and self.is_host:
                return not obj.is_superuser
            # Guest administrators can change only guest users
            elif self.is_administrator and not self.is_host:
                return (not obj.is_superuser) \
                       and (not obj.is_host) \
                       and (
                               (self.fdp_organization is None and obj.fdp_organization)
                               or (self.fdp_organization == obj.fdp_organization)
                       )
            # Otherwise can't edit
            else:
                return False
        # Not changing a user
        else:
            return True

    def has_perm(self, perm, obj=None):
        """ Overwrites user permission check to ensure that if delete if performed in the admin interface, then
        permission is given.

        Without this, all DELETE actions are denied.

        :param perm:
        :param obj:
        :return:
        """
        # default permissions check (if already true, then short circuit)
        if super(FdpUser, self).has_perm(perm=perm, obj=obj):
            return self.only_user_alter_matching_user(obj=obj)
        # default check did not grant permission
        else:
            dot = '.'
            # check if permission sought is following format: app.***
            if perm and dot in perm:
                perm_pieces = perm.split(dot, 1)
                if len(perm_pieces) == 2:
                    app = perm_pieces[0]
                    underscore = '_'
                    # check if permission sought is following format: app.action_model
                    if app in settings.APPS_IN_ADMIN and perm_pieces[1] and underscore in perm_pieces[1]:
                        action_model = perm_pieces[1].split(underscore, 1)
                        if len(action_model) == 2:
                            action = action_model[0]
                            model = action_model[1]
                            # check if action is delete and a model is specified
                            if action.lower() == 'delete' and model:
                                return self.has_admin_perm(obj=obj)
            return False

    def has_admin_perm(self, obj=None):
        """ Checks whether user has admin permissions, in the context of changing, deleting or viewing objects.

        :param obj: Object that will be changed, deleted or viewed.
        :return: True if user has admin permissions, false otherwise.
        """
        return self.has_admin_access and self.only_user_alter_matching_user(obj=obj)

    def check_password(self, raw_password):
        """ Ensures that users who are authenticated only through external authentication mechanisms, such as Azure
        Active Directory cannot use a username and password combination to login through the Django model backend.

        :param raw_password: Raw password entered by user.
        :return: True if raw password matches password in database, false otherwise. Will always return false for
        externally authenticated users.
        """
        return super(FdpUser, self).check_password(raw_password=raw_password) and not self.only_external_auth

    objects = FdpUserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        """Defines string representation for a FDP user.

        :return: String representation of a FDP user.
        """
        return self.email

    @staticmethod
    def can_view_core(user):
        """ Checks whether a user can view core FDP data.

        :param user: User to check.
        :return: True if user can view core FDP data, false otherwise.
        """
        return user.is_active and user.is_authenticated

    @staticmethod
    def can_view_admin(user):
        """ Checks whether a user can view admin FDP data.

        :param user: User to check.
        :return: True if user can view admin FDP data, false otherwise.
        """
        return user.is_active and (user.is_administrator or user.is_superuser)

    @staticmethod
    def can_view_host_admin(user):
        """ Checks whether a user can view host and admin only data and access corresponding functionality.

        :param user: User to check.
        :return: True if user can view host and admin only data, and access corresponding functionality,
        false otherwise.
        """
        return user.is_active and ((user.is_administrator and user.is_host) or user.is_superuser)

    def get_accessible_users(self):
        """ Retrieves a filtered queryset of users that the user can access.

        :return: Queryset filtered for users that the user can access.
        """
        queryset = FdpUser.objects.all()
        # Superuser can access any user
        if self.is_superuser:
            return queryset
        # Host administrators can access all users  but super users
        elif self.is_administrator and self.is_host:
            return queryset.exclude(is_superuser=True)
        # Guest administrators can change only guest users
        elif self.is_administrator and not self.is_host:
            queryset = queryset.exclude(is_superuser=True).exclude(is_host=True)
            # user belongs to an organization
            if self.fdp_organization:
                return queryset.filter(fdp_organization=self.fdp_organization)
            # user does not belong to an organization
            else:
                return queryset.filter(fdp_organization__isnull=True)
        # Otherwise can't access
        raise Exception(_('FdpUser.get_accessible_users(...) should only be called for administrators and superusers.'))

    @classmethod
    def filter_for_admin(cls, queryset, user):
        """ Filter a queryset for the admin interfaces.

        Assumes that queryset has already been filtered for direct confidentiality, i.e. whether user has access to
        each record based on the record's level of confidentiality. E.g. a confidentiable queryset of Person.

        Can be used to filter for indirect confidentiality, i..e whether user has access to each record based on other
        relevant records' levels of confidentiality. E.g. a queryset of PersonAlias linking to a confidentiality
        queryset of Person.

        :param queryset: Queryset to filter.
        :param user: User for which to filter queryset.
        :return: Filtered queryset.
        """
        accessible_queryset = user.get_accessible_users()
        return queryset.filter(pk__in=accessible_queryset)

    @property
    def has_azure_active_directory_social_auth(self):
        """ Checks whether the Django database backend has a record corresponding to a user's authentication through
        Microsoft Azure Active Directory.

        :return: True if the record exists, false otherwise.
        """
        social_auth_qs = getattr(self, 'social_auth', None)
        if social_auth_qs is not None:
            return social_auth_qs.filter(provider=AbstractConfiguration.azure_active_directory_provider).exists()
        else:
            return False

    @classmethod
    def is_user_azure_authenticated(cls, user):
        """ Checks if a user has been properly authenticated through the Azure Active Directory authentication backend.

        The control statement logic should be similar to the control statement logic found in
        the method do_missing_social_auth_check(...).

        :param user: User whose authentication status should be checked.
        :return: True if user has been properly authenticated through Azure Active Directory, false otherwise.
        """
        # user is defined
        # AND user is not anonymous
        # AND user is authenticated
        # AND user is not superuser
        # and user is only externally authenticated
        # and user has at least one social authentication through the Azure Active Directory
        if user \
                and (not user.is_anonymous) \
                and user.is_authenticated \
                and user.is_active \
                and (not user.is_superuser) \
                and user.only_external_auth \
                and user.has_azure_active_directory_social_auth:
            return True
        # user is not externally authenticated
        else:
            return False

    @classmethod
    def do_missing_social_auth_check(cls, user):
        """ Checks if a user is intended to be authenticated through the Azure Active Directory authentication backend,
        but does not have a corresponding social auth record in the Django database.

        In other words, the user has "only_external_auth" property set to True, but has no corresponding valid record in
        the "social_auth_usersocialauth" database table.

        In this case, remove the active session records from the database, to force the user to log in again.

        The control statement logic should be similar to the control statement logic found in
        the method is_user_azure_authenticated(...).

        :param user: User whose social authentication association should be checked.
        :return: Nothing.
        """
        # user is defined
        # AND user is not anonymous
        # AND user is authenticated
        # AND user is not superuser
        # and user is only externally authenticated
        # and user has no social authentication through the Azure Active Directory
        if user \
                and (not user.is_anonymous) \
                and user.is_authenticated \
                and user.is_active \
                and (not user.is_superuser) \
                and user.only_external_auth \
                and not user.social_auth.filter(
                    provider=AbstractConfiguration.azure_active_directory_provider
                ).exists():
            # Only expected to be here if database is an unexpected state for a particular user. For example, the user's
            # social auth association may have been manually deleted from the "social_auth_usersocialauth" database
            # table. To resolve this unexpected state, cycle through all active sessions and remove those for this user.
            # This is expected to force the user to login thereby fixing the unexpected state.
            for session in Session.objects.filter(expire_date__gte=now()):
                # decode each session and compare with the user's primary key
                if str(user.pk) == str((session.get_decoded()).get('_auth_user_id')):
                    # Once the session is removed, the next HTTPs request that the user submits, will be responded to
                    # with a: Bad Request (400)
                    # The corresponding error that is logged will be: The request's session was deleted before the
                    # request completed. The user may have logged out in a concurrent request, for example.
                    session.delete()

    def agrees_to_eula(self):
        """ Records in the database the timestamp when a user agrees to the end-user license agreement.

        :return: Nothing.
        """
        self.agreed_to_eula = now()
        self.full_clean()
        self.save()

    class Meta:
        db_table = '{d}fdp_user'.format(d=settings.DB_PREFIX)
        verbose_name = _('FDP User')
        ordering = ['email']


class PasswordResetManager(models.Manager):
    """ Manager for logs of password resets for which users.

    """
    def create_password_reset(self, email, request):
        """ Creates a record of a password reset for a specific user.

        :param email: Email of user whose password is being reset.
        :param request: Http request object.
        :return: Record logging the password reset for a specific user.
        """
        # email did not match any user
        if not FdpUser.objects.filter(email=email).exists():
            mail_admins(
                subject=_('Password Reset for Unknown Email'),
                message=_(
                    'A password reset has been requested for {e}. There is no user in the database with this email. '
                    'No action was taken.'.format(e=email)
                )
            )
            return None
        user = FdpUser.objects.get(email=email)
        # password reset requested for inactive user
        if not user.is_active:
            mail_admins(
                subject=_('Password Reset for Inactive User'),
                message=_(
                    'A password reset has been requested for {e}. This user is inactive and so cannot log in. '
                    'No action was taken.'.format(e=user.email)
                )
            )
            return None
        # retrieve IP address
        ip_address = AbstractIpAddressValidator.get_ip_address(request=request)
        # create password reset record
        password_reset = self.create(fdp_user=user, ip_address=ip_address)
        # validate password reset record
        password_reset.full_clean()
        # save password reset record
        password_reset.save()
        return password_reset


class PasswordReset(models.Model):
    """ Logs every password reset performed by FDP users.

    Attributes:
        :fdp_user (fk): FDP user performing password reset.
        :timestamp (datetime): Automatically added timestamp for when the password was reset.
        :ip_address (str): IP address of client from which password reset was initiated.
    """
    fdp_user = models.ForeignKey(
        FdpUser,
        on_delete=models.CASCADE,
        related_name='password_resets',
        related_query_name='password_reset',
        blank=False,
        null=False,
        help_text=_('FDP user whose password was reset'),
        verbose_name=_('FDP user')
    )

    timestamp = models.DateTimeField(
        null=False,
        blank=False,
        auto_now_add=True,
        help_text=_('Automatically added timestamp for when the password was reset'),
        verbose_name=_('timestamp')
    )

    ip_address = models.CharField(
        null=False,
        blank=True,
        validators=[validate_ipv46_address],
        max_length=50,
        help_text=_('IP address of client from which password reset was initiated'),
        verbose_name=_('IP address')
    )

    objects = PasswordResetManager()

    def __str__(self):
        """Defines string representation for a password reset log.

        :return: String representation of a password reset log.
        """
        return '{f} {u} {a} {d}'.format(
            f=_('for'),
            u=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_user'),
            a=_('at'),
            d=self.timestamp
        )

    @classmethod
    def can_reset_password(cls, user, ip_address, email):
        """ Checks whether the password for a particular user be reset from a particular IP address.

        :param user: User whose password should be reset. Ignored if None.
        :param ip_address: IP address from which password reset is requested.
        :param email: Email  address of user whose password should be reset. Ignored if None.
        :return: True if password can be reset, false otherwise.
        """
        one_day_ago = now() - timedelta(days=1)
        m = settings.MAX_PWD_RESET_PER_USER_PER_DAY
        t_kwargs = {'timestamp__gte': one_day_ago}
        # init that user's password can be reset
        can_user_be_reset = True
        # if user is logged in, then check whether they can reset password for themselves (user must be active)
        if user:
            can_user_be_reset = cls.objects.filter(fdp_user_id=user.pk, **t_kwargs).count() < m and user.is_active \
                                and user.has_changeable_password
        # if user is not logged in, then check if email specified can have password reset (user must be active)
        if email:
            can_user_be_reset = can_user_be_reset and cls.objects.filter(
                fdp_user__email=email, **t_kwargs
            ).count() < m and FdpUser.objects.filter(email=email, is_active=True).exists() and (
                FdpUser.objects.get(email=email)
            ).has_changeable_password
        return can_user_be_reset and (
            (not ip_address) or cls.objects.filter(
                ip_address=ip_address, timestamp__gte=one_day_ago
            ).count() < settings.MAX_PWD_RESET_PER_IP_ADDRESS_PER_DAY
        )

    @staticmethod
    def logout(request):
        """ Logs a user out of their account.

        :param request: Http request object.
        :return: Nothing.
        """
        # Logs out user
        logout(request)

    @classmethod
    def invalidate_password_logout(cls, user, request):
        """ Invalidates user's current password and logs user out of their account.

        :param user: User whose password should be invalidated and who should be logged out.
        :param request: Http request object.
        :return: Nothing.
        """
        # only reset password if it can be changed or reset
        if user.has_changeable_password:
            # Resets the user's password
            pwd_len = 128
            max_tries = 10
            password = get_random_string(length=pwd_len)
            while max_tries > 0:
                try:
                    user.set_password(password)
                    user.full_clean()
                    user.save()
                    max_tries = 0
                    break
                except ValidationError:
                    max_tries -= 1
                    password = get_random_string(length=pwd_len)
        # log user out of their account
        cls.logout(request=request)
        return

    class Meta:
        db_table = '{d}password_reset'.format(d=settings.DB_PREFIX)
        verbose_name = _('Password reset')
        ordering = ['timestamp']


class EulaManager(models.Manager):
    """ Manager for a end-user license agreement (EULA).

    """
    def get_current_eula(self):
        """ Retrieves the current EULA.

        :return: Model instance representing current EULA, or None if no EULAs exist.
        """
        # no EULAs exist
        if not self.all().exists():
            return None
        # some EULAs exist
        else:
            return self.all().order_by('-timestamp').first()


class Eula(Metable):
    """ An end-user license agreement (EULA).

    Attributes:
        :file (file): File containing EULA.
        :timestamp (datetime): Automatically added timestamp for when EULA was uploaded.
    """
    file = models.FileField(
        upload_to=f'{AbstractUrlValidator.EULA_BASE_URL}%Y/%m/%d/%H/%M/%S/',
        blank=False,
        null=False,
        validators=[
            AbstractFileValidator.validate_eula_file_size,
            AbstractFileValidator.validate_eula_file_extension
        ],
        max_length=AbstractFileValidator.MAX_EULA_FILE_LEN,
        verbose_name=_('File'),
        help_text=_(
            'End-user license agreement file. Should be less than {s}MB.'
            '<br>Allowed file formats: {allowed_file_formats}'.format(
                s=AbstractFileValidator.get_megabytes_from_bytes(
                    num_of_bytes=AbstractConfiguration.max_eula_file_bytes()
                ),
                allowed_file_formats=AbstractConfiguration().supported_eula_file_types_str()
            )
        ),
        unique=True,
    )

    timestamp = models.DateTimeField(
        null=False,
        blank=False,
        auto_now_add=True,
        help_text=_('Automatically added timestamp for when EULA was uploaded'),
        verbose_name=_('timestamp')
    )

    @property
    def status(self):
        """ Retrieves the status for the EULA.

        If this is the most recently added EULA, it is considered current. Otherwise, it is considered archived.

        :return: String representation of the status for the EULA.
        """
        current_eula = Eula.objects.get_current_eula()
        return _('Current') if current_eula is None or self.timestamp >= current_eula.timestamp else _('Archived')

    objects = EulaManager()

    def __str__(self):
        """ Defines string representation for an end-user license agreement.

        :return: String representation for an end-user license agreement.
        """
        added = _('added')
        return f'{self.get_verbose_name()} {added} {self.timestamp}'

    class Meta:
        db_table = '{d}eula'.format(d=settings.DB_PREFIX)
        verbose_name = _('EULA')
        verbose_name_plural = _('EULAs')
        ordering = ['-timestamp']
