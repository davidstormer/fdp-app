from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.db.models import Q, Prefetch
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from inheritable.models import Archivable, Descriptable, AbstractForeignKeyValidator, AbstractKnownInfo, \
    AbstractFileValidator, Confidentiable, AbstractUrlValidator, AbstractExactDateBounded, Linkable, \
    AbstractConfiguration
from supporting.models import ContentType, Court, ContentIdentifierType, ContentCaseOutcome, \
    AttachmentType, SituationRole, Allegation, AllegationOutcome
from fdpuser.models import FdpOrganization
from core.models import Person, Incident
from django.urls import reverse


class Attachment(Confidentiable, Descriptable):
    """ An attachment is a file, link or other external content that provides information for an incident.

    Attributes:
        :name (str): Name of attachment. If a user-friendly name is not available, use the file name, title of article,
        etc.
        :file (file): Uploaded attachment as the attachment file. Ignore if linking an attachment via the web.
        :extension (str): File extension for attachment file. Ignore if linking an attachment via the web.
        :link (str): URL for an attachment linked via the web. Ignore if uploading a file as the attachment.
        :type (fk): Category for attachment.
        :fdp_organizations (m2m): FDP organizations, which have exclusive access to attachment. Leave blank if all
        registered users can access.

    Properties:
        :file_name (str): Name of the file, if it exists, for the attachment.
    """
    name = models.CharField(
        null=False,
        blank=False,
        max_length=settings.MAX_NAME_LEN,
        help_text=_(
            'Name of attachment. If a user-friendly name is not available, use the file name, title of article, etc.'
        ),
        verbose_name=_('name')
    )

    file = models.FileField(
        upload_to='{b}%Y/%m/%d/%H/%M/%S/'.format(b=AbstractUrlValidator.ATTACHMENT_BASE_URL),
        blank=True,
        null=False,
        help_text=_(
            'Uploaded file as the attachment. Should be less than {s}MB. '
            'Ignore if linking an attachment via the web.'.format(
                s=AbstractFileValidator.get_megabytes_from_bytes(
                    num_of_bytes=AbstractConfiguration.max_attachment_file_bytes()
                )
            )
        ),
        validators=[
            AbstractFileValidator.validate_attachment_file_size,
            AbstractFileValidator.validate_attachment_file_extension
        ],
        max_length=AbstractFileValidator.MAX_ATTACHMENT_FILE_LEN
    )

    extension = models.CharField(
        null=False,
        blank=True,
        max_length=10,
        help_text=_('File extension for attachment. Ignore if linking an attachment via the web.'),
        verbose_name=_('file extension')
    )

    link = models.URLField(
        null=False,
        blank=True,
        help_text=_('URL for an attachment linked via the web. Ignore if uploading a file as the attachment.'),
        verbose_name=_('web link')
    )

    type = models.ForeignKey(
        AttachmentType,
        on_delete=models.SET_NULL,
        related_name='attachments',
        related_query_name='attachment',
        blank=True,
        null=True,
        help_text=_('Category for attachment'),
        verbose_name=_('type')
    )

    fdp_organizations = models.ManyToManyField(
        FdpOrganization,
        related_name='attachments',
        related_query_name='attachment',
        db_table='{d}attachment_fdp_organization'.format(d=settings.DB_PREFIX),
        blank=True,
        help_text=_('FDP organizations, which have exclusive access to attachment. '
                    'Leave blank if all registered users can access.'),
        verbose_name=_('organization access')
    )

    def __file_name(self):
        """ Retrieves the name of the file, if it exists, for the attachment.

        :return: Name of the file.
        """
        return '' if not self.file else AbstractFileValidator.get_file_name(file_path=self.file.name)

    @property
    def file_name(self):
        """ Retrieves the name of the file, if it exists, for the attachment.

        :return: Name of the file.
        """
        return self.__file_name()

    #: Fields to display in the model form.
    form_fields = ['type', 'name', 'file', 'link'] + Confidentiable.confidentiable_form_fields

    def __str__(self):
        """Defines string representation for an attachment.

        :return: String representation of an attachment.
        """
        return self.name

    def clean(self):
        """ Ensure that attachment path is unique, and also that it contains no directory traversal.

        :return: Nothing
        """
        super(Attachment, self).clean()
        # record has a file field defined
        if self.file:
            file_path = str(self.file)
            # full path when relative and root paths are joined
            full_path = AbstractFileValidator.join_relative_and_root_paths(
                relative_path=file_path,
                root_path=settings.MEDIA_ROOT
            )
            # verify that path is a real path (i.e. no directory traversal takes place)
            # will raise exception if path is not a real path
            AbstractFileValidator.check_path_is_expected(
                relative_path=file_path,
                root_path=settings.MEDIA_ROOT,
                expected_path_prefix=full_path,
                err_msg=_('Attachment file path may contain directory traversal'),
                err_cls=ValidationError
            )
            # attachments with this file
            attachments_qs = Attachment.objects.filter(file=file_path)
            # record already exists, i.e. has primary key in database
            pk = getattr(self, 'pk', None)
            if pk:
                attachments_qs = attachments_qs.exclude(pk=pk)
            # check that no attachments with this file field exist
            if attachments_qs.exists():
                raise ValidationError(_('The path for this file is already taken'))

    @classmethod
    def get_prefetch(cls, user, prefix, to_attr):
        """ Retrieves a Prefetch object for Attachment model.

        :param prefix: Prefix for related name through which to retrieve attachments.
        :param user: User requesting Prefetch object.
        :param to_attr: Name of attribute to which to assign the Prefetch object.
        :return: Prefetch object for Attachment model.
        """
        return Prefetch(
            '{p}attachments'.format(p=prefix if prefix else ''),
            queryset=cls.active_objects.all().filter_for_confidential_by_user(user=user).filter(
                Q(type__isnull=True) | Q(**cls.get_active_filter(prefix='type'))
            ).select_related('type'),
            to_attr=to_attr
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
        db_table = '{d}attachment'.format(d=settings.DB_PREFIX)
        verbose_name = _('attachment')
        ordering = ['name']


class Content(Confidentiable, Descriptable):
    """ A content which provides information for an incident.

    May be a lawsuit, social media post, newspaper article, etc.

    Attributes:
        :name (str): Name of content. Use this for the article headline, report title or other user-friendly name.
        :attachments (m2m): Attachments from which content was derived.
        :incidents (m2m): Incidents based on this content.
        :type (fk): Category for content.
        :link (str): Link for this content.
        :publication_date (date): Date content was published.
        :fdp_organizations (m2m): FDP organizations, which have exclusive access to content.
        Leave blank if all registered users can access.

    Properties:
        :all_attachments (str): A comma separated list of all attachments from which abstract attachment was derived.
        :all_incidents (str): A comma separated list of all incidents based on abstract attachment.
    """
    @property
    def all_attachments(self):
        """ Retrieve a comma separated list of all attachments from which abstract attachment was derived.

        :return: Comma separated list of all attachments.
        """
        # return self.__all_attachments()
        # Disabled to preserve confidentiality
        return 'Disabled'

    @property
    def all_incidents(self):
        """ Retrieve a comma separated list of all incidents based on abstract attachment.

        :return: Comma separated list of all incidents.
        """
        # return self.__all_incidents()
        # Disabled to preserve confidentiality
        return 'Disabled'

    name = models.CharField(
        null=False,
        blank=True,
        default='',
        max_length=settings.MAX_NAME_LEN,
        help_text=_(
            'Name of content. Use this for the article headline, report title or other user-friendly name.'
        ),
        verbose_name=_('name')
    )

    attachments = models.ManyToManyField(
        Attachment,
        related_name='contents',
        related_query_name='content',
        db_table='{d}content_attachment'.format(d=settings.DB_PREFIX),
        blank=True,
        help_text=_('Attachments from which content was derived'),
        verbose_name=_('attachments')
    )

    incidents = models.ManyToManyField(
        Incident,
        related_name='contents',
        related_query_name='content',
        db_table='{d}content_incident'.format(d=settings.DB_PREFIX),
        blank=True,
        help_text=_('Incidents based on this content'),
        verbose_name=_('incidents')
    )

    type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        related_name='contents',
        related_query_name='content',
        blank=True,
        null=True,
        help_text=_('Category for content'),
        verbose_name=_('type')
    )

    link = models.URLField(
        null=False,
        blank=True,
        default='',
        help_text=_('URL from which content was retrieved'),
        verbose_name=_('web link'),
        max_length=AbstractUrlValidator.MAX_LINK_LEN
    )

    publication_date = models.DateField(
        null=True,
        blank=True,
        help_text=_('Date content was published'),
        verbose_name=_('publication date')
    )

    fdp_organizations = models.ManyToManyField(
        FdpOrganization,
        related_name='contents',
        related_query_name='content',
        db_table='{d}content_fdp_organization'.format(d=settings.DB_PREFIX),
        blank=True,
        help_text=_('FDP organizations, which have exclusive access to content. '
                    'Leave blank if all registered users can access.'),
        verbose_name=_('organization access')
    )

    #: Fields to display in the model form.
    form_fields = [
                      'type', 'name', 'link', 'publication_date', 'description'
                  ] + Confidentiable.confidentiable_form_fields

    #: Fields to display in the form linking attachments to content.
    content_attachment_form_fields = ['attachment_name', 'attachment', 'content']

    #: Fields to display in the form linking incidents to content.
    content_incident_form_fields = ['incident_name', 'incident', 'content']

    def __str__(self):
        """ Defines string representation for a content.

        :return: String representation of a content.
        """
        return '{t} - {p}'.format(
            t=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='type'),
            p=self.name if self.name else getattr(self, 'pk', 'unnamed')
        )

    def clean(self):
        """ Ensure that if link is defined, it is unique.

        :return: Nothing
        """
        super(Content, self).clean()
        # link is defined
        if self.link:
            # content with this link
            content_qs = self.__class__.objects.filter(link=self.link)
            # record already exists, i.e. has primary key in database
            pk = getattr(self, 'pk', None)
            if pk:
                # exclude itself
                content_qs = content_qs.exclude(pk=pk)
            # check that no content with this link field value exist
            if content_qs.exists():
                raise ValidationError(_('Content with this link already exists'))

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
            pk__in=Content.active_objects.filter(
                Q(
                    attachments__in=Attachment.filter_for_admin(
                        queryset=Attachment.active_objects.all().filter_for_confidential_by_user(user=user),
                        user=user
                    )
                )
                |
                Q(attachments__isnull=True)
            )
        )

    @property
    def get_edit_url(self):
        return reverse('changing:edit_content', kwargs={"pk": self.pk})

    class Meta:
        db_table = '{d}content'.format(d=settings.DB_PREFIX)
        verbose_name = _('content')
        ordering = ['type', 'publication_date', 'name']
        constraints = [
            # unique content link if field is not blank
            models.UniqueConstraint(fields=['link'], name='uq_content_link', condition=Q(~Q(link__iexact='')))
        ]


class ContentIdentifier(Confidentiable, Descriptable):
    """ Identifier for content such as a lawsuit number, IAB case number, etc.

    Attributes:
        :identifier (str): Identifier number such as the lawsuit number, IAB case number, or similar.
        :content_identifier_type (fk): Type of identifier, such as lawsuit number, IAB case number or similar.
        :content (fk): Content linked to this identifier.
        :fdp_organizations (m2m): FDP organizations, which have exclusive access to attachment. Leave blank if all
        registered users can access.
    """
    identifier = models.CharField(
        null=False,
        blank=False,
        help_text=_('Identifier number, such as the lawsuit number, IAB case number, or similar'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('identifier')
    )

    content_identifier_type = models.ForeignKey(
        ContentIdentifierType,
        on_delete=models.CASCADE,
        related_name='content_identifiers',
        related_query_name='content_identifier',
        blank=False,
        null=False,
        help_text=_('Context for identifier, such as lawsuit, IAB case, or similar'),
        verbose_name=_('content identifier type')
    )

    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        related_name='content_identifiers',
        related_query_name='content_identifier',
        blank=False,
        null=False,
        help_text=_('Content linked to this identifier'),
        verbose_name=_('Content')
    )

    fdp_organizations = models.ManyToManyField(
        FdpOrganization,
        related_name='content_identifiers',
        related_query_name='content_identifier',
        db_table='{d}content_identifier_fdp_organization'.format(d=settings.DB_PREFIX),
        blank=True,
        help_text=_('FDP organizations, which have exclusive access to content identifier. '
                    'Leave blank if all registered users can access.'),
        verbose_name=_('organization access')
    )

    #: Fields to display in the model form.
    form_fields = ['content_identifier_type', 'identifier', 'content'] + Confidentiable.confidentiable_form_fields

    def __str__(self):
        """ Defines string representation for a content identifier.

        :return: String representation of a content identifier.
        """
        return '{t} #{n} {f} {p}'.format(
            t=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='content_identifier_type'),
            n=self.identifier,
            f=_('for'),
            p=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='content')
        )

    @classmethod
    def get_prefetch(cls, user, prefix, to_attr):
        """ Retrieves a Prefetch object for ContentIdentifier model.

        :param user: User requesting Prefetch object.
        :param prefix: Prefix for related name through which to retrieve content identifiers.
        :param to_attr: Name of attribute to which to assign the Prefetch object.
        :return: Prefetch object for ContentIdentifier model.
        """
        return Prefetch(
            '{p}content_identifiers'.format(p=prefix if prefix else ''),
            queryset=cls.active_objects.all().filter_for_confidential_by_user(user=user).filter(
                **cls.get_active_filter(prefix='content_identifier_type')
            ).select_related(
                'content_identifier_type'
            ),
            to_attr=to_attr
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
            content__in=Content.filter_for_admin(
                queryset=Content.active_objects.all().filter_for_confidential_by_user(user=user),
                user=user
            )
        )

    class Meta:
        db_table = '{d}content_identifier'.format(d=settings.DB_PREFIX)
        verbose_name = _('content identifier')
        unique_together = ('content', 'content_identifier_type', 'identifier')
        ordering = ['content', 'content_identifier_type']


class ContentCase(Archivable, AbstractExactDateBounded):
    """ Case content such as lawsuit and other cases brought against officer(s) or agency(ies).

    Attributes:
        :outcome (fk): Outcome of case, such as dismissed, or similar.
        :court (fk): Court or agency in which case was pursued.
        :settlement_amount (decimal): Amount received by plaintiff as settlement.
        :content (fk): Content based on this case.
    """
    outcome = models.ForeignKey(
        ContentCaseOutcome,
        on_delete=models.SET_NULL,
        related_name='content_cases',
        related_query_name='content_case',
        blank=True,
        null=True,
        help_text=_('Outcome of lawsuit such as dismissed or similar'),
        verbose_name=_('case disposition')
    )

    court = models.ForeignKey(
        Court,
        on_delete=models.SET_NULL,
        related_name='content_cases',
        related_query_name='content_case',
        blank=True,
        null=True,
        help_text=_('Court or agency in which case was pursued'),
        verbose_name=_('court')
    )

    settlement_amount = models.DecimalField(
        null=True,
        blank=True,
        max_digits=12,
        decimal_places=2,
        help_text=_('Amount received by plaintiff as settlement'),
        verbose_name=_('settlement amount')
    )

    content = models.OneToOneField(
        Content,
        on_delete=models.CASCADE,
        related_name='content_case',
        related_query_name='content_case',
        blank=False,
        null=False,
        help_text=_('Content based on this lawsuit'),
        verbose_name=_('Content')
    )

    #: Fields to display in the model form.
    form_fields = ['outcome', 'settlement_amount', 'court', 'content']

    def __str__(self):
        """Defines string representation for a case content.

        :return: String representation of a case content.
        """
        return '{a} {f} {c}'.format(
            a=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='court'),
            f=_('for'),
            c=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='content')
        )

    def clean(self):
        """ Verifies that start date comes before end date.

        :return: Nothing.
        """
        # Check that start date is before end date
        self._check_start_date_before_end_date()

    @classmethod
    def get_prefetch(cls, prefix, to_attr):
        """ Retrieves a Prefetch object for ContentCase model.

        :param prefix: Prefix for related name through which to retrieve content cases.
        :param to_attr: Name of attribute to which to assign the Prefetch object.
        :return: Prefetch object for ContentCase model.
        """
        return Prefetch(
            '{p}content_case'.format(p=prefix if prefix else ''),
            queryset=cls.active_objects.all().filter(
                    Q(Q(**cls.get_active_filter(prefix='outcome')) | Q(outcome__isnull=True))
                    &
                    Q(Q(**cls.get_active_filter(prefix='court')) | Q(court__isnull=True))
                ).select_related(*cls.get_select_related()),
            to_attr=to_attr
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
            content__in=Content.filter_for_admin(
                queryset=Content.active_objects.all().filter_for_confidential_by_user(user=user),
                user=user
            )
        )

    @staticmethod
    def get_select_related():
        """ Retrieves a list of positional arguments that can be passed into Django's select_related(...) function when
        building an content case queryset.

        :return: List of positional arguments.
        """
        return ['outcome', 'court']

    class Meta:
        db_table = '{d}content_case'.format(d=settings.DB_PREFIX)
        verbose_name = _('content case')
        ordering = ['content']


class ContentPerson(Archivable, Descriptable, Linkable, AbstractKnownInfo):
    """ Link between person and a case content such as an attorney for a lawsuit, plaintiff for a lawsuit, etc.

    Attributes:
        :person (fk): Person linked to case content.
        :situation_role (fk): Context with which person is linked to content, such as attorney,
        plaintiff or similar.
        :content (fk): Content linked to this person.
    """
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='content_persons',
        related_query_name='content_person',
        blank=False,
        null=False,
        help_text=_('Person linked to a content'),
        verbose_name=_('person')
    )

    situation_role = models.ForeignKey(
        SituationRole,
        on_delete=models.SET_NULL,
        related_name='content_persons',
        related_query_name='content_person',
        blank=True,
        null=True,
        help_text=_('Context with which person is linked to content, such as attorney, plaintiff or similar'),
        verbose_name=_('situation role')
    )

    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        related_name='content_persons',
        related_query_name='content_person',
        blank=False,
        null=False,
        help_text=_('Content linked to this person'),
        verbose_name=_('content')
    )

    #: Fields to display in the model form.
    form_fields = ['situation_role', 'person', 'person_name', 'content', 'is_guess']

    def __str__(self):
        """Defines string representation for a content person.

        :return: String representation of a content person.
        """
        return '{t} {p} {f} {c}'.format(
            t=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='situation_role'),
            p=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='person'),
            f=_('for'),
            c=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='content')
        )

    @classmethod
    def get_filtered_queryset(cls, user, person_filter_dict, content_filter_dict):
        """ Retrieves a filtered queryset of content persons for both content and persons.

        :param user: User requesting queryset.
        :param person_filter_dict: Dictionary that can be expanded into keyword arguments for optional filtering of
        persons.
        :param content_filter_dict: Dictionary that can be expanded into keyword arguments for optional filtering of
        contents.
        :return: Filtered queryset of content persons.
        """
        # mandatory person filtering
        persons = Person.active_objects.all().filter_for_confidential_by_user(user=user)
        # optional person filtering
        if person_filter_dict:
            persons = persons.filter(**person_filter_dict)
        # mandatory content filtering
        contents = Content.active_objects.filter(
            Q(Q(type__isnull=True) | Q(**ContentType.get_active_filter(prefix='type')))
        ).filter_for_confidential_by_user(user=user)
        # optional content filtering
        if content_filter_dict:
            contents = contents.filter(**content_filter_dict)
        return cls.active_objects.all().filter(
            Q(person__in=persons)
            &
            Q(content__in=contents)
            &
            Q(Q(situation_role__isnull=True) | Q(**SituationRole.get_active_filter(prefix='situation_role')))
        ).select_related('content', 'person', 'situation_role')

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
            content__in=Content.filter_for_admin(
                queryset=Content.active_objects.all().filter_for_confidential_by_user(user=user),
                user=user
            ),
            person__in=Person.filter_for_admin(
                queryset=Person.active_objects.all().filter_for_confidential_by_user(user=user),
                user=user
            )
        )

    class Meta:
        db_table = '{d}content_person'.format(d=settings.DB_PREFIX)
        verbose_name = _('link between content and person')
        verbose_name_plural = _('links between contents and people')
        unique_together = ('content', 'situation_role', 'person')
        ordering = ['content', 'situation_role', 'person']


class ContentPersonAllegation(Archivable, Descriptable):
    """ Allegations against a person linked to content.

    Attributes:
        :content_person (fk): Person linked to content.
        :allegation (fk): Allegation against the person in the context of a particular content.
        :allegation_outcome (fk): Outcome of allegation against the person.
        :allegation_count (int): Number of same allegations with this outcome against person.

    """
    content_person = models.ForeignKey(
        ContentPerson,
        on_delete=models.CASCADE,
        related_name='content_person_allegations',
        related_query_name='content_person_allegation',
        blank=False,
        null=False,
        help_text=_('Person and content that provide the context for the allegation'),
        verbose_name=_('person-content link')
    )

    allegation = models.ForeignKey(
        Allegation,
        on_delete=models.CASCADE,
        related_name='content_person_allegations',
        related_query_name='content_person_allegation',
        blank=False,
        null=False,
        help_text=_('Allegation against the person in the context of the content'),
        verbose_name=_('allegation')
    )

    allegation_outcome = models.ForeignKey(
        AllegationOutcome,
        on_delete=models.SET_NULL,
        related_name='content_person_allegations',
        related_query_name='content_person_allegation',
        blank=True,
        null=True,
        help_text=_('Outcome of allegation against the person in the context of the content'),
        verbose_name=_('allegation outcome')
    )

    allegation_count = models.PositiveSmallIntegerField(
        null=False,
        blank=False,
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text=_('Number of same allegations with this outcome against the person in the context of the content'),
        verbose_name=_('allegation count')
    )

    #: Fields to display in the model form.
    form_fields = ['allegation', 'allegation_outcome', 'allegation_count', 'content_person']

    def __str__(self):
        """ Defines string representation for an allegation against a person linked to content.

        :return: String representation of an allegation against a person linked to content.
        """
        return '{a} {n} {b}'.format(
            a=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='allegation'),
            n=_('by'),
            b=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='content_person')
        )

    @staticmethod
    def get_select_related():
        """ Retrieves a list of positional arguments that can be passed into Django's select_related(...) function when
        building an content person allegation queryset.

        :return: List of positional arguments.
        """
        return ['allegation', 'allegation_outcome']

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
            content_person__in=ContentPerson.filter_for_admin(queryset=ContentPerson.active_objects.all(), user=user)
        )

    class Meta:
        db_table = '{d}content_person_allegation'.format(d=settings.DB_PREFIX)
        verbose_name = _('Allegation against person linked to content')
        verbose_name_plural = _('Allegations against people linked to contents')
        unique_together = ('content_person', 'allegation', 'allegation_outcome')
        ordering = ['content_person', 'allegation']


class ContentPersonPenalty(Archivable, Descriptable):
    """ Penalties for a person linked to content.

    Attributes:
        :content_person (fk): Person linked to content.
        :penalty_requested (str): Penalty requested for person linked to content.
        :penalty_received (str): Penalty received for person linked to content.
        :discipline_date (date): Date that penalty was imposed for person linked to content.
    """
    content_person = models.ForeignKey(
        ContentPerson,
        on_delete=models.CASCADE,
        related_name='content_person_penalties',
        related_query_name='content_person_penalty',
        blank=False,
        null=False,
        help_text=_('Person and content that provide the context for the penalty'),
        verbose_name=_('person-content link')
    )

    penalty_requested = models.CharField(
        null=False,
        blank=True,
        default='',
        help_text=_('Penalty requested for person linked to content'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('penalty requested')
    )

    penalty_received = models.CharField(
        null=False,
        blank=True,
        default='',
        help_text=_('Penalty received for person linked to content'),
        max_length=500,
        verbose_name=_('penalty received')
    )

    discipline_date = models.DateField(
        null=True,
        blank=True,
        help_text=_('Date that penalty was imposed for person linked to content'),
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('discipline date')
    )

    #: Fields to display in the model form.
    form_fields = ['penalty_requested', 'penalty_received', 'discipline_date', 'content_person']

    def __str__(self):
        """ Defines string representation for a penalty for a person linked to content.

        :return: String representation of a penalty for a person linked to content.
        """
        return '{req} {a}, {rec} {b} {o} {d} {f} {c}'.format(
            req=_('requested'),
            a=self.penalty_requested,
            rec=_('and received'),
            b=self.penalty_received,
            o=_('on'),
            d=self.discipline_date,
            f=_('for'),
            c=AbstractForeignKeyValidator.stringify_foreign_key(obj=self, foreign_key='content_person')
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
            content_person__in=ContentPerson.filter_for_admin(queryset=ContentPerson.active_objects.all(), user=user)
        )

    class Meta:
        db_table = '{d}content_person_penalty'.format(d=settings.DB_PREFIX)
        verbose_name = _('Penalty for person linked to content')
        verbose_name_plural = _('Penalties for people linked to contents')
        ordering = ['content_person', 'discipline_date']
