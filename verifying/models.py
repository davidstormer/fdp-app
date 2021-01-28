from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from inheritable.models import Descriptable, Archivable, AbstractForeignKeyValidator
from core.models import Person
from sourcing.models import Content, ContentCase
from fdpuser.models import FdpUser


class AbstractVerify(Descriptable):
    """ Base class from which all verification classes inherit.

    Verifying allows a user to assert the correctness of information such as an officer's shield number.

    Attributes:
        :timestamp (datetime): Date and time that user verified the information.

    """
    timestamp = models.DateTimeField(
        null=False,
        blank=False,
        auto_now_add=True,
        help_text=_('Automatically added timestamp for when the user verified the information'),
        verbose_name=_('timestamp')
    )

    class Meta:
        abstract = True


class VerifyType(Archivable):
    """ Type of verification performed by user.

    Attributes:
        :name (str): Name of verification type.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of verification type'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a verification type.

        :return: String representation of a verification type.
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
        db_table = '{d}verify_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('verification type')
        ordering = ['name']


class VerifyPerson(Archivable, AbstractVerify):
    """ Verifications of person information such as officer shield numbers, tax IDs, etc.

    Attributes:
        :type (fk): Category of verification performed for person.
        :person (fk): Person whose information was verified by user.
        :fdp_user (fk): User who verified the information.
    """
    type = models.ForeignKey(
        VerifyType,
        on_delete=models.CASCADE,
        related_name='verify_persons',
        related_query_name='verify_person',
        blank=False,
        null=False,
        help_text=_('Category of verification performed for person'),
        verbose_name=_('type')
    )

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='verify_persons',
        related_query_name='verify_person',
        blank=False,
        null=False,
        help_text=_('Person whose information was verified by user'),
        verbose_name=_('person')
    )

    fdp_user = models.ForeignKey(
        FdpUser,
        on_delete=models.CASCADE,
        related_name='verify_persons',
        related_query_name='verify_person',
        blank=False,
        null=False,
        help_text=_('User who verified the information'),
        verbose_name=_('FDP user')
    )

    def __str__(self):
        """Defines string representation for a person verification.

        :return: String representation of a person verification.
        """
        return '{b} {u} {o} {p}'.format(
            b=_('by'),
            u=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_user'),
            o=_('on'),
            p=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='person')
        )

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
        return queryset.filter(
            fdp_user__in=user.get_accessible_users(),
            person__in=Person.active_objects.all().filter_for_confidential_by_user(user=user)
        )

    class Meta:
        db_table = '{d}verify_person'.format(d=settings.DB_PREFIX)
        verbose_name = _('person verification')
        ordering = ['timestamp', 'person', 'fdp_user']


class VerifyContentCase(Archivable, AbstractVerify):
    """ Verifications of content case information such as a lawsuit, IAB case, or brady disclosure, etc.

    Attributes:
        :type (fk): Category of verification performed for content case.
        :content (fk): Content case whose information was verified by user.
        :fdp_user (fk): User who verified the information.
    """
    type = models.ForeignKey(
        VerifyType,
        on_delete=models.CASCADE,
        related_name='verify_content_cases',
        related_query_name='verify_content_case',
        blank=False,
        null=False,
        help_text=_('Category of verification performed for content case'),
        verbose_name=_('type')
    )

    content_case = models.ForeignKey(
        ContentCase,
        on_delete=models.CASCADE,
        related_name='verify_content_cases',
        related_query_name='verify_content_case',
        blank=False,
        null=False,
        help_text=_('Content case which was verified by user'),
        verbose_name=_('content case')
    )

    fdp_user = models.ForeignKey(
        FdpUser,
        on_delete=models.CASCADE,
        related_name='verify_content_cases',
        related_query_name='verify_content_case',
        blank=False,
        null=False,
        help_text=_('User who verified the information'),
        verbose_name=_('FDP user')
    )

    def __str__(self):
        """Defines string representation for a content case verification.

        :return: String representation of a content case verification.
        """
        return '{b} {u} {o} {c}'.format(
            b=_('by'),
            u=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_user'),
            o=_('on'),
            c=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='content_case')
        )

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
        return queryset.filter(
            fdp_user__in=user.get_accessible_users(),
            content_case__content__in=Content.active_objects.all().filter_for_confidential_by_user(user=user)
        )

    class Meta:
        db_table = '{d}verify_content_case'.format(d=settings.DB_PREFIX)
        verbose_name = _('content case verification')
        ordering = ['timestamp', 'content_case', 'fdp_user']
