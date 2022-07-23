from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from inheritable.models import Archivable, ArchivableSearchCategory, AbstractForeignKeyValidator


class AbstractRelationshipType(models.Model):
    """ Base class from which all relationship type classes inherit.

    Relationship types categorize the relationships among persons, among groupings and among officers.

    Attributes:
        :hierarchy (str): Specifies for this relationship type whether the subject is superior to the object,
        vice-versa, or there is no hierarchy.

    """
    RIGHT_IS_SUPERIOR = '/'
    LEFT_IS_SUPERIOR = '\\'
    NO_HIERARCHY = '-'

    HIERARCHY_CHOICES = (
        (NO_HIERARCHY, 'No hierarchy'),
        (LEFT_IS_SUPERIOR, 'Subject is superior'),
        (RIGHT_IS_SUPERIOR, 'Object is superior'),
    )

    hierarchy = models.CharField(
        max_length=1,
        choices=HIERARCHY_CHOICES,
        default=NO_HIERARCHY,
        help_text=_('Specify for this relationship type whether the subject is superior to the object, '
                    'vice-versa, or there is no hierarchy'),
        verbose_name=_('hierarchy')
    )

    class Meta:
        abstract = True


class State(Archivable):
    """ State for contact information.

    Attributes:
        :name (str): Name of state.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of state'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a state.

        :return: String representation of a state.
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
        db_table = '{d}state'.format(d=settings.DB_PREFIX)
        verbose_name = _('State')
        ordering = ['name']


class TraitType(Archivable):
    """ Type of trait can be used to group traits such as those that refer to race or gender.

    Attributes:
        :name (str): Name of person's trait type.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Trait type to group traits, such as gender, race or similar'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a person trait type.

        :return: String representation of a person trait type.
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
        db_table = '{d}trait_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('trait type')
        ordering = ['name']


class Trait(Archivable):
    """ Trait that can be used to describe a person, such as a gender, race or other characteristic value.

    Attributes:
        :name (str): Name of person's trait.
        :type (fk): Category used to group trait.
    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Trait to describe a person in the system, such as a gender (e.g. male), '
                    'race (e.g. black), or other characterstic (e.g. homeless)'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
    )

    type = models.ForeignKey(
        TraitType,
        on_delete=models.SET_NULL,
        related_name='traits',
        related_query_name='trait',
        blank=True,
        null=True,
        help_text=_('Category used to group trait'),
        verbose_name=_('type')
    )

    def __str__(self):
        """Defines string representation for a person trait.

        :return: String representation of a person trait.
        """
        return '{n} ({t})'.format(
            n=self.name,
            t=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='type')
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
        return queryset

    class Meta:
        db_table = '{d}trait'.format(d=settings.DB_PREFIX)
        verbose_name = _('trait')
        unique_together = ('type', 'name')
        ordering = ['type', 'name']


class PersonRelationshipType(Archivable, AbstractRelationshipType):
    """ Defines a relationship between two persons.

    Attributes:
        :name (str): Name of the relationship between two persons.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of the relationship between two persons'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a relationship between two persons.

        :return: String representation of a relationship between two persons.
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
        db_table = '{d}person_relationship_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('type of relationship between two persons')
        verbose_name_plural = _('types of relationships between two persons')
        ordering = ['name']


class County(ArchivableSearchCategory):
    """ County in state.

    Attributes:
        :name (str): Name of county.
        :state (fk): State in which county exists.
    """
    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name='counties',
        related_query_name='county',
        blank=False,
        null=False,
        help_text=_('State in which county exists'),
        verbose_name=_('state')
    )

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of county'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name')
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
        return queryset

    def __str__(self):
        """Defines string representation for a county.

        :return: String representation of a county.
        """
        return '{c}, {s}'.format(
            c=self.name,
            s=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='state')
        )

    class Meta:
        db_table = '{d}county'.format(d=settings.DB_PREFIX)
        verbose_name = _('county')
        verbose_name_plural = _('counties')
        unique_together = ('state', 'name')
        ordering = ['state', 'name']


class Location(Archivable):
    """ Locations where incidents can occur.

    Attributes:
        :county (fk): County for location.
        :address (str): Address for location.

    """

    county = models.ForeignKey(
        County,
        on_delete=models.CASCADE,
        related_name='locations',
        related_query_name='location',
        blank=False,
        null=False,
        help_text=_('If county not on list <a href="/admin/supporting/county/add/" target="_blank">add it here</a>'),
        verbose_name=_('county')
    )

    address = models.CharField(
        null=False,
        blank=True,
        help_text=_('Full address, cross street, or partial address'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('address')
    )

    #: Fields to display in the model form.
    form_fields = ['county', 'address']

    def __str__(self):
        """Defines string representation for a location.

        :return: String representation of a location.
        """
        return '{c}'.format(c=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='county')) \
            if not self.address else '{a}, {c}'.format(
                a=self.address,
                c=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='county')
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
        return queryset

    class Meta:
        db_table = '{d}location'.format(d=settings.DB_PREFIX)
        verbose_name = _('Location')
        ordering = ['county']
        unique_together = ('county', 'address')


class PersonIdentifierType(Archivable):
    """ Categorizes an identifier for a person, such as driver's license number, passport number, etc.

    Attributes:
        :name (str): Name of category for person identifier.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of category for person identifier such as a driver\'s license number or passport number.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a person identifier type.

        :return: String representation of a person identifier type.
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
        db_table = '{d}person_identifier_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('person identifier type')
        ordering = ['name']


class Title(ArchivableSearchCategory):
    """ Title such as detective, fdptain, etc.

    Attributes:
        :name (str): Name of title.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of title'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a title.

        :return: String representation of a title.
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
        db_table = '{d}title'.format(d=settings.DB_PREFIX)
        verbose_name = _('title')
        ordering = ['name']


class GroupingRelationshipType(Archivable, AbstractRelationshipType):
    """ Defines a relationship between two groupings.

    Attributes:
        :name (str): Name of the relationship between two groupings.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of the relationship between two groupings'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a relationship between two groupings.

        :return: String representation of a relationship between two groupings.
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
        db_table = '{d}grouping_relationship_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('type of relationship between two groupings')
        verbose_name_plural = _('types of relationships between two groupings')
        ordering = ['name']


class PersonGroupingType(Archivable):
    """ Categorizes a link between a person and grouping, such as attorney, etc.

    Attributes:
        :name (str): Name of category for link between a person and grouping.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Category for a link between a person and grouping'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a person grouping type.

        :return: String representation of a person grouping type.
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
        db_table = '{d}person_grouping_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('person grouping type')
        ordering = ['name']


class IncidentLocationType(Archivable):
    """ Type of location where incidents can occur.

    Attributes:
        :name (str): Name of incident location type.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of incident location type'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for an incident location type.

        :return: String representation of an incident location type.
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
        db_table = '{d}incident_location_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('incident location type')
        ordering = ['name']


class EncounterReason(Archivable):
    """ Reason for encounter during incident.

    Attributes:
        :name (str): Name of encounter reason.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of encounter reason'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for an encounter reason.

        :return: String representation of an encounter reason.
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
        db_table = '{d}encounter_reason'.format(d=settings.DB_PREFIX)
        verbose_name = _('encounter reason')
        ordering = ['name']


class IncidentTag(Archivable):
    """ Tag categorizing an incident.

    Attributes:
        :name (str): Name of incident tag.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of incident tag'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for an incident tag.

        :return: String representation of an incident tag.
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
        db_table = '{d}incident_tag'.format(d=settings.DB_PREFIX)
        verbose_name = _('incident tag')
        ordering = ['name']


class PersonIncidentTag(Archivable):
    """ Tag categorizing a link between a person and an incident.

    Attributes:
        :name (str): Name of tag for a link between a person and an incident.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of tag for a link between a person and an incident'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a tag for a link between a person and an incident.

        :return: String representation of a tag for a link between a person and an incident.
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
        db_table = '{d}person_incident_tag'.format(d=settings.DB_PREFIX)
        verbose_name = _('person incident tag')
        ordering = ['name']


class Allegation(Archivable):
    """ Allegations such as abuse, discourtesy, etc.

    Attributes:
        :name (str): Name of allegation.
    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of allegation'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for an allegation.

        :return: String representation of an allegation.
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
        db_table = '{d}allegation'.format(d=settings.DB_PREFIX)
        verbose_name = _('allegation')
        ordering = ['name']


class AllegationOutcome(Archivable):
    """ An allegation outcome such as dismissed, etc.

    Attributes:
        :name (str): Name of allegation outcome.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of allegation outcome'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for an allegation outcome.

        :return: String representation of an allegation outcome.
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
        db_table = '{d}allegation_outcome'.format(d=settings.DB_PREFIX)
        verbose_name = _('allegation outcome')
        ordering = ['name']


class ContentType(Archivable):
    """ Category for content such as news article, lawsuit, etc.

    Attributes:
        :name (str): Name of content type.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of content type'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a content type.

        :return: String representation of a content type.
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
        db_table = '{d}content_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('content type')
        ordering = ['name']


class Court(Archivable):
    """ Court hearing a particular case, such as the Supreme Court, etc.

    Attributes:
        :name (str): Name of court.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of court'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a court.

        :return: String representation of a court.
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
        db_table = '{d}court'.format(d=settings.DB_PREFIX)
        verbose_name = _('court')
        ordering = ['name']


class ContentIdentifierType(Archivable):
    """ Categorizes an identifier for a content, such as lawsuit number or IAB case number, etc.

    Attributes:
        :name (str): Name of category for content identifier.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of category for content identifier such as a lawsuit number or IAB case number.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a content identifier type.

        :return: String representation of a content identifier type.
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
        db_table = '{d}content_identifier_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('content identifier type')
        ordering = ['name']


class ContentCaseOutcome(Archivable):
    """ Outcome for content case such as lawsuit dismissed, etc.

    Attributes:
        :name (str): Name of outcome for content case.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of case outcome'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a content case outcome.

        :return: String representation of a content case outcome.
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
        db_table = '{d}content_case_outcome'.format(d=settings.DB_PREFIX)
        verbose_name = _('content case outcome')
        ordering = ['name']


class AttachmentType(Archivable):
    """ A category of attachment, such as Brady Disclosure, lawsuit, etc.

    Attributes:
        :name (str): Name of attachment type.

    """

    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of attachment type'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for an attachment type.

        :return: String representation of an attachment type.
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
        db_table = '{d}attachment_type'.format(d=settings.DB_PREFIX)
        verbose_name = _('attachment type')
        ordering = ['name']


class SituationRole(Archivable):
    """ Categorizes a link between a person and online content, generic content, case content and incidents.

    Attributes:
        :name (str): Name of category for a link between a person and online content, generic content, case content and
        incidents.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of category for a link between a person and online content, '
                    'generic content, case content and incidents.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a link between a person and online content, generic content, case content
        and incidents.

        :return: String representation of a link between a person and online content, generic content, case content
        and incidents.
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
        db_table = '{d}situation_role'.format(d=settings.DB_PREFIX)
        verbose_name = _('situation role')
        ordering = ['name']


class LeaveStatus(Archivable):
    """ Categorizes a leave status for a person's payment, such as active or ceased.

    Attributes:
        :name (str): Name of leave status for a person's payment.

    """
    name = models.CharField(
        null=False,
        blank=False,
        help_text=_('Name of leave status for a person\'s payment such as active or ceased.'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('name'),
        unique=True
    )

    def __str__(self):
        """Defines string representation for a leave status.

        :return: String representation of a leave status.
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
        db_table = '{d}leave_status'.format(d=settings.DB_PREFIX)
        verbose_name = _('leave status')
        verbose_name_plural = _('leave statuses')
        ordering = ['name']
