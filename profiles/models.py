from abc import ABC

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.core.validators import validate_ipv46_address
from inheritable.models import AbstractForeignKeyValidator, AbstractIpAddressValidator, Archivable
from fdpuser.models import FdpUser
from core.models import Person, Grouping


class AbstractSearch(models.Model):
    """ Base class from which all search classes inherit.

    Search classes record searches that users perform.

    Attributes:
        :parsed_search_criteria (json): Search criteria entered by user after it is parsed.
        :timestamp (datetime): Automatically added timestamp recording when user performed search.
        :ip_address (str): IP address of client from which search was performed.
        :num_of_results (int): Total number of records matching search criteria.
    """
    parsed_search_criteria = models.JSONField(
        blank=False,
        null=False,
        help_text=_('Search criteria entered by user after it is parsed'),
        verbose_name=_('parsed search criteria')
    )

    timestamp = models.DateTimeField(
        null=False,
        blank=False,
        auto_now_add=True,
        help_text=_('Automatically added timestamp recording when user performed search'),
        verbose_name=_('timestamp')
    )

    ip_address = models.CharField(
        null=False,
        blank=True,
        validators=[validate_ipv46_address],
        max_length=50,
        help_text=_('IP address of client from which search was performed'),
        verbose_name=_('IP address')
    )

    num_of_results = models.PositiveIntegerField(
        null=False,
        blank=False,
        help_text=_('Total number of records matching search criteria'),
        verbose_name=_('number of search results')
    )

    class Meta:
        abstract = True


class AbstractView(models.Model):
    """ Base class from which all view classes inherit.

    View classes record profiles that users view.

    Attributes:
        :timestamp (datetime): Automatically added timestamp recording when user viewed profile.
        :ip_address (str): IP address of client from which profile was viewed.
    """
    timestamp = models.DateTimeField(
        null=False,
        blank=False,
        auto_now_add=True,
        help_text=_('Automatically added timestamp recording when user viewed profile'),
        verbose_name=_('timestamp')
    )

    ip_address = models.CharField(
        null=False,
        blank=True,
        validators=[validate_ipv46_address],
        max_length=50,
        help_text=_('IP address of client from which profile was viewed'),
        verbose_name=_('IP address')
    )

    class Meta:
        abstract = True


class OfficerSearchManager(models.Manager):
    """ Manager for officer searches performed by FDP users.

    """
    def create_officer_search(self, num_of_results, parsed_search_criteria, fdp_user, request):
        """ Creates a record of an officer search performed by a FDP user.

        :param num_of_results: Total number of records matching the search criteria.
        :param parsed_search_criteria: Dictionary of search criteria entered by user after it is parsed.
        :param fdp_user: FDP user performing the officer search.
        :param request: Http request object.
        :return: Record of an officer search performed by a FDP user.
        """
        # retrieve IP address
        ip_address = AbstractIpAddressValidator.get_ip_address(request=request)
        # create officer search record
        officer_search = self.create(
            parsed_search_criteria=parsed_search_criteria,
            fdp_user=fdp_user,
            ip_address=ip_address,
            num_of_results=num_of_results
        )
        # validate officer search record
        officer_search.full_clean()
        # save officer search record
        officer_search.save()
        return officer_search


class OfficerSearch(AbstractSearch):
    """ Searches for officers that users have performed.

    Attributes:
        :fdp_user (fk): FDP user performing search for officer.

    """
    fdp_user = models.ForeignKey(
        FdpUser,
        on_delete=models.CASCADE,
        related_name='officer_searches',
        related_query_name='officer_search',
        blank=False,
        null=False,
        help_text=_('FDP user performing the search'),
        verbose_name=_('FDP user')
    )

    objects = OfficerSearchManager()

    def __str__(self):
        """Defines string representation for an officer search.

        :return: String representation of an officer search.
        """
        return '{b} {u} {a} {t}'.format(
            b=_('by'),
            u=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_user'),
            a=_('at'),
            t=self.timestamp
        )

    class Meta:
        db_table = '{d}officer_search'.format(d=settings.DB_PREFIX)
        verbose_name = _('Officer search')
        verbose_name_plural = _('Officer searches')
        ordering = ['timestamp']


class OfficerViewManager(models.Manager):
    """ Manager for officer profile views performed by FDP users.

    """
    def create_officer_view(self, person, fdp_user, request):
        """ Creates a record of an officer profile viewed by a FDP user.

        :param person: Person whose profile is viewed.
        :param fdp_user: FDP user viewing the officer profile.
        :param request: Http request object.
        :return: Record of an officer profile viewed by a FDP user.
        """
        # retrieve IP address
        ip_address = AbstractIpAddressValidator.get_ip_address(request=request)
        # create officer profile view record
        officer_view = self.create(person=person, fdp_user=fdp_user, ip_address=ip_address)
        # validate officer profile view record
        officer_view.full_clean()
        # save officer profile view record
        officer_view.save()
        return officer_view


class OfficerView(AbstractView):
    """ Officer profiles that have been viewed by users.

    Attributes:
        :fdp_user (fk): FDP user viewing officer profile.
        :person (fk): Person whose officer profile was viewed.

    """
    fdp_user = models.ForeignKey(
        FdpUser,
        on_delete=models.CASCADE,
        related_name='officer_views',
        related_query_name='officer_view',
        blank=False,
        null=False,
        help_text=_('FDP user viewing the officer profile'),
        verbose_name=_('FDP user')
    )

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='officer_views',
        related_query_name='officer_view',
        blank=False,
        null=False,
        help_text=_('Person whose officer profile was viewed'),
        verbose_name=_('person')
    )

    objects = OfficerViewManager()

    def __str__(self):
        """Defines string representation for an officer profile view.

        :return: String representation of an officer profile view.
        """
        return '{o} {v} {u} {a} {t}'.format(
            o=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='person'),
            v=_('viewed by'),
            u=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_user'),
            a=_('at'),
            t=self.timestamp
        )

    class Meta:
        db_table = '{d}officer_view'.format(d=settings.DB_PREFIX)
        verbose_name = _('Officer view')
        verbose_name_plural = _('Officer views')
        ordering = ['timestamp']


class CommandSearchManager(models.Manager):
    """ Manager for command searches performed by FDP users.

    """
    def create_command_search(self, num_of_results, parsed_search_criteria, fdp_user, request):
        """ Creates a record of a command search performed by a FDP user.

        :param num_of_results: Total number of records matching the search criteria.
        :param parsed_search_criteria: Dictionary of search criteria entered by user after it is parsed.
        :param fdp_user: FDP user performing the command search.
        :param request: Http request object.
        :return: Record of a command search performed by a FDP user.
        """
        # retrieve IP address
        ip_address = AbstractIpAddressValidator.get_ip_address(request=request)
        # create command search record
        command_search = self.create(
            parsed_search_criteria=parsed_search_criteria,
            fdp_user=fdp_user,
            ip_address=ip_address,
            num_of_results=num_of_results
        )
        # validate command search record
        command_search.full_clean()
        # save command search record
        command_search.save()
        return command_search


class CommandSearch(AbstractSearch):
    """ Searches for commands that users have performed.

    Attributes:
        :fdp_user (fk): FDP user performing search for command.

    """
    fdp_user = models.ForeignKey(
        FdpUser,
        on_delete=models.CASCADE,
        related_name='command_searches',
        related_query_name='command_search',
        blank=False,
        null=False,
        help_text=_('FDP user performing the search'),
        verbose_name=_('FDP user')
    )

    objects = CommandSearchManager()

    def __str__(self):
        """Defines string representation for a command search.

        :return: String representation of a command search.
        """
        return '{b} {u} {a} {t}'.format(
            b=_('by'),
            u=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_user'),
            a=_('at'),
            t=self.timestamp
        )

    class Meta:
        db_table = '{d}command_search'.format(d=settings.DB_PREFIX)
        verbose_name = _('Command search')
        verbose_name_plural = _('Command searches')
        ordering = ['timestamp']


class CommandViewManager(models.Manager):
    """ Manager for command profile views performed by FDP users.

    """
    def create_command_view(self, grouping, fdp_user, request):
        """ Creates a record of a command profile viewed by a FDP user.

        :param grouping: Grouping whose profile is viewed.
        :param fdp_user: FDP user viewing the command profile.
        :param request: Http request object.
        :return: Record of a command profile viewed by a FDP user.
        """
        # retrieve IP address
        ip_address = AbstractIpAddressValidator.get_ip_address(request=request)
        # create command profile view record
        command_view = self.create(grouping=grouping, fdp_user=fdp_user, ip_address=ip_address)
        # validate command profile view record
        command_view.full_clean()
        # save command profile view record
        command_view.save()
        return command_view


class CommandView(AbstractView):
    """ Command profiles that have been viewed by users.

    Attributes:
        :fdp_user (fk): FDP user viewing command profile.
        :grouping (fk): Grouping whose command profile was viewed.

    """
    fdp_user = models.ForeignKey(
        FdpUser,
        on_delete=models.CASCADE,
        related_name='command_views',
        related_query_name='command_view',
        blank=False,
        null=False,
        help_text=_('FDP user viewing the command profile'),
        verbose_name=_('FDP user')
    )

    grouping = models.ForeignKey(
        Grouping,
        on_delete=models.CASCADE,
        related_name='command_views',
        related_query_name='command_view',
        blank=False,
        null=False,
        help_text=_('Grouping whose command profile was viewed'),
        verbose_name=_('grouping')
    )

    objects = CommandViewManager()

    def __str__(self):
        """Defines string representation for a command profile view.

        :return: String representation of a command profile view.
        """
        return '{o} {v} {u} {a} {t}'.format(
            o=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='grouping'),
            v=_('viewed by'),
            u=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='fdp_user'),
            a=_('at'),
            t=self.timestamp
        )

    class Meta:
        db_table = '{d}command_view'.format(d=settings.DB_PREFIX)
        verbose_name = _('Command view')
        verbose_name_plural = _('Command views')
        ordering = ['timestamp']


class SiteSettingKeys:
    """This is the official list of site setting key names"""

    CUSTOM_TEXT_BLOCKS__PROFILE_PAGE_TOP = 'custom_text_blocks-profile_page_top'
    CUSTOM_TEXT_BLOCKS__PROFILE_INCIDENTS = 'custom_text_blocks-profile_incidents'
    CUSTOM_TEXT_BLOCKS__GLOBAL_FOOTER = 'custom_text_blocks-global_footer'
    CUSTOM_TEXT_BLOCKS__GLOBAL_FOOTER_RIGHT = 'custom_text_blocks-global_footer_right'


class SiteSetting(Archivable):
    key = models.CharField(max_length=settings.MAX_NAME_LEN)
    value = models.JSONField()

    @classmethod
    def filter_for_admin(cls, queryset, user):
        """ Required for the Archivable parent class...
        """
        return queryset

    def __str__(self):
        return f"{self.key}: {self.value}"


def get_site_setting(setting_name: str) -> str:
    try:
        return SiteSetting.objects.get(key=setting_name).value
    except SiteSetting.DoesNotExist:
        return None


def set_site_setting(setting_name: str, value: str):
    try:
        existing_setting = SiteSetting.objects.get(key=setting_name)
        existing_setting.value = value
        existing_setting.save()
    except SiteSetting.DoesNotExist:
        SiteSetting.objects.create(
            key=setting_name,
            value=value
        )
