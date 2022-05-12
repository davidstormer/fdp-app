import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.views.generic import TemplateView

from inheritable.models import AbstractUrlValidator, AbstractSearchValidator, \
    AbstractFileValidator
from inheritable.views import SecuredSyncFormView, SecuredSyncListView, SecuredSyncDetailView, SecuredSyncView, \
    SecuredSyncTemplateView, AdminSyncFormView
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.http import urlquote, urlunquote
from django.urls import reverse, reverse_lazy
from django.http import QueryDict, HttpResponse
from .models import OfficerSearch, OfficerView, CommandSearch, CommandView, SiteSetting, get_site_setting, \
    set_site_setting, SiteSettingKeys
from .forms import OfficerSearchForm, CommandSearchForm, SiteSettingsForm
from inheritable.models import Archivable, AbstractSql, AbstractImport
from core.models import Person, PersonIdentifier, PersonGrouping, Grouping, GroupingAlias
from sourcing.models import Content, ContentPerson, ContentPersonAllegation
from supporting.models import Allegation
# Load a customized algorithm for person searches
PersonProfileSearch = AbstractImport.load_profile_search(
    file_setting='FDP_PERSON_PROFILE_SEARCH_FILE',
    class_setting='FDP_PERSON_PROFILE_SEARCH_CLASS',
    file_default='def_person',
    class_default='PersonProfileSearch'
)
# Load a customized algorithm for grouping searches
GroupingProfileSearch = AbstractImport.load_profile_search(
    file_setting='FDP_GROUPING_PROFILE_SEARCH_FILE',
    class_setting='FDP_GROUPING_PROFILE_SEARCH_CLASS',
    file_default='def_grouping',
    class_default='GroupingProfileSearch'
)


class IndexTemplateView(SecuredSyncTemplateView):
    """ Page that allows users to select whether to search by commands or officers.

    """
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        """ Adds the title, description and user details to the view context.

        :param kwargs:
        :return: Context for view, including title, description and user details.
        """
        context = super(IndexTemplateView, self).get_context_data(**kwargs)
        context.update({
            'title': _('What are you searching for?'),
            'description': _('Select whether to search for officers or commands.')
        })
        return context


class OfficerSearchFormView(SecuredSyncFormView):
    """ Page that allows users to search for officers and corresponding information.

    """
    template_name = 'officer_search.html'
    form_class = OfficerSearchForm

    def __init__(self, **kwargs):
        """ Initializes the form property that will be set once the form is validated and passed to the method building
        the success URL.

        :param args:
        :param kwargs:
        """
        super(OfficerSearchFormView, self).__init__(**kwargs)
        self.form = None

    @staticmethod
    def _get_search_querystring(search_text):
        """ Sets the querystring used to specify the original unparsed search criteria.

        :param search_text: A single string of search criteria entered by the user.
        :return: Querystring used to specify the original unparsed search criteria.
        """
        querystring = QueryDict('', mutable=True)
        # record original search criteria
        original_search = search_text
        # set the querystring
        querystring = AbstractUrlValidator.add_encrypted_value_to_querystring(
            querystring=querystring, key=AbstractUrlValidator.GET_ORIGINAL_PARAM, value_to_add=original_search
        )
        return querystring

    def get_success_url(self):
        """ Build link to search results containing the original unparsed search criteria as querystring GET parameter.

        :return: Link to search results for original unparsed search criteria.
        """
        search_text = self.form.cleaned_data['search']
        # process the search string entered by the user
        querystring = self._get_search_querystring(search_text=search_text)
        return '{url}?{querystring}'.format(
            url=reverse('profiles:officer_search_results'),
            querystring=querystring.urlencode()
        )

    def get_context_data(self, **kwargs):
        """ Adds the title, description and search form to the view context.

        :param kwargs:
        :return: Context for view, including title, description and search form.
        """
        context = super(OfficerSearchFormView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Officer Search'),
            'description': _('Search for officers and corresponding information.')
        })
        return context

    def form_valid(self, form):
        """ Displays paginated list of officers matching search criteria.

        Called when a valid form data is submitted via POST method.

        Returns a HttpResponse object.

        :param form: Search form that was submitted by user.
        :return:
        """
        self.form = form
        return super(OfficerSearchFormView, self).form_valid(form=form)


class OfficerSearchResultsListView(SecuredSyncListView):
    """ Page that allows users to browse search results displaying a filtered and paginated list of officers.

    """
    template_name = 'officer_search_results.html'
    model = Person
    context_object_name = 'officer_list'

    def __init__(self, **kwargs):
        """ Initialize the queryset count to zero, list of results to empty, the search criteria to nothing, and the
        search class that contains the searching algorithm.

        :param kwargs:
        """
        super(OfficerSearchResultsListView, self).__init__(**kwargs)
        self.__count = 0
        self.__result_list = []
        self.__search_class = None

    def __parse_officer_filters(self):
        """ Parses out the search criteria specified in the GET parameter that will be used to filter officers.

        :return: Nothing.
        """
        g = self.request.GET
        keys = list(g.keys())
        # retrieve a mapping from unencrypted keys to encrypted keys
        key_mapping = AbstractUrlValidator.get_key_mapping(list_of_keys=keys)
        # get original search criteria
        original_search_text = AbstractUrlValidator.get_unencrypted_value_from_querystring(
            querystring=g,
            key=AbstractUrlValidator.GET_ORIGINAL_PARAM,
            default_value='',
            key_mapping=key_mapping
        )
        # definition used for searching algorithm
        self.__search_class = PersonProfileSearch(
            original_search_criteria=original_search_text,
            unique_table_suffix=PersonProfileSearch.get_unique_table_suffix(user=self.request.user)
        )
        # parse the search criteria
        self.__search_class.common_parse_search_criteria()

    def __define_count_query(self):
        """ Defines the count version of the searching query.

        Sets the following properties:
         - self._count_params
         - self._sql_count_query

        :return: Nothing.
        """
        # SELECT COUNT(*) FROM ... SQL query to count persons matching search criteria
        self._sql_count_query = """ {sql_temp_table} SELECT COUNT(DISTINCT "{person}"."id") {sql_from}; """.format(
            sql_temp_table=self.__search_class.temp_table_query,
            person=Person.get_db_table(),
            sql_from=self.__search_class.sql_from_query
        )
        self._count_params = self.__search_class.temp_table_params + self.__search_class.from_params

    def __define_select_query(self):
        """ Defines the select version of the searching query.

        Sets the following properties:
         - self._select_params
         - self._sql_select_query

        :return: Nothing.
        """
        # SELECT * FROM ... SQL query to retrieve persons matching search criteria
        self._sql_select_query = """
            {sql_temp_table}
            SELECT
                A."id",
                A."name",
                MAX(A."score"),
                (
                    SELECT string_agg(ZPI."identifier", ', ')
                    FROM "{person_identifier}" AS ZPI
                    WHERE ZPI."person_id" = A."id"
                    AND ZPI.{active_filter}
                    GROUP BY ZPI."person_id"
                ) AS "ids",
                ( {title_sql} ) AS "title",
                (
                    SELECT string_agg(DISTINCT ZPG."name", ', ')
                    FROM "{grouping}" AS ZPG
                    INNER JOIN "{person_grouping}" AS ZPPG
                    ON ZPG."id" = ZPPG."grouping_id"
                    AND ZPPG."person_id" = A."id"
                    AND ZPPG.{active_filter}                    
                    WHERE ZPG.{active_filter}
                ) AS "groupings"
            FROM
                (
                SELECT
                    "{person}"."id",
                    "{person}"."name" AS "name",
                    {sql_score}
                {sql_from}
            ) A
            GROUP BY A."id", A."name"
            ORDER BY MAX(A."score") DESC
            LIMIT {max};
        """.format(
            active_filter=Archivable.ACTIVE_FILTER,
            sql_temp_table=self.__search_class.temp_table_query,
            title_sql=Person.get_title_sql(person_table_alias='A'),
            person=Person.get_db_table(),
            person_identifier=PersonIdentifier.get_db_table(),
            person_grouping=PersonGrouping.get_db_table(),
            grouping=Grouping.get_db_table(),
            sql_from=self.__search_class.sql_from_query,
            sql_score=self.__search_class.sql_score_query,
            max=AbstractSearchValidator.MAX_WIZARD_SEARCH_RESULTS
        )
        self._select_params = self.__search_class.temp_table_params \
            + self.__search_class.score_params \
            + self.__search_class.from_params

    def __get_officer_results(self):
        """ Retrieves the filtered list of officers, and the count of the officers matching the search criteria.

        Sets two properties defining the filtered and ordered list of officers matching search criteria,
        limited to the top X results.

        Property #1 is self.__count, which stores the total number of results matching the search criteria.

        Property #2 is self.__result_list, which stores the filtered and ordered list of officer matching search
        criteria, limited to the top X results.

        :return: Nothing.
        """
        # user performing the search
        user = self.request.user
        # parse out the filtering criteria for officers
        self.__parse_officer_filters()
        # define the body of the query
        self.__search_class.common_define_sql_query_body(user=user)
        # define the scoring for rows in the query
        self.__search_class.common_define_sql_query_score()
        # define the count version of the searching query
        self.__define_count_query()
        # define the select version of the searching query
        self.__define_select_query()
        # perform count query
        persons_count = AbstractSql.exec_single_val_sql(sql_query=self._sql_count_query, sql_params=self._count_params)
        # perform select query
        persons = Person.objects.raw(self._sql_select_query, self._select_params)
        self.__count = persons_count
        self.__result_list = persons

    def get_context_data(self, **kwargs):
        """ Adds the title, description and search form to the view context.

        :param kwargs:
        :return: Context for view, including title, description and search form.
        """
        context = super(OfficerSearchResultsListView, self).get_context_data(**kwargs)
        request = self.request
        OfficerSearch.objects.create_officer_search(
            num_of_results=self.__count,
            parsed_search_criteria=self.__search_class.parsed_search_criteria,
            fdp_user=request.user,
            request=request
        )
        current_search_querystring = request.GET.urlencode()
        querystring = QueryDict('', mutable=True)
        querystring.update({AbstractUrlValidator.GET_PREV_URL_PARAM: urlquote(current_search_querystring)})
        context.update({
            'title': _('Officer Search Results'),
            'description': _('Browse a list of officers matching the search criteria.'),
            'search': self.__search_class.parsed_search_criteria,
            'back_link_querystring': querystring.urlencode(),
            'queryset_count': self.__count,
            'max_results': AbstractSearchValidator.MAX_WIZARD_SEARCH_RESULTS,
            'has_more': (self.__count > AbstractSearchValidator.MAX_WIZARD_SEARCH_RESULTS)
        })
        return context

    def get_queryset(self):
        """ Filters the officer queryset by the search criteria.

        :return: Officer queryset filtered by the search criteria.
        """
        self.__get_officer_results()
        return self.__result_list


class OfficerSearchRoundupView(SecuredSyncTemplateView):
    template_name = "officer_search_roundup.html"

    def get(self, request, *args, **kwargs):

        results = Person.objects.search_all_fields('', request.user)
        related_groups = (
            Grouping.objects.filter(is_law_enforcement=True)
            .filter(person_grouping__person__in=results)
            .order_by('name')
            .distinct()
        )
        paginator = Paginator(results, 50)

        page_number = request.POST.get('page')
        page_obj = paginator.get_page(page_number)
        return self.render_to_response({
            'title': 'Officer Search',
            'query': '',
            'sort': 'relevance',
            'page_obj': page_obj,
            'number_of_results': results.count(),
            'groups': related_groups,
        })

    # Handle searches via POST so that the query string is kept out of the URL (security)
    def post(self, request, *args, **kwargs):
        query_string = request.POST.get('q')
        sort = request.POST.get('sort') or 'relevance'
        page_number = request.POST.get('page')

        try:
            group = Grouping.objects.get(pk=request.POST.get('group'))
        except Grouping.DoesNotExist:
            group = None
        except ValueError:
            group = None

        results = Person.objects.search_all_fields(query_string, request.user)

        if group:
            results = results.filter(person_grouping__grouping=group).distinct()

        if sort == 'name':
            results = results.order_by('name')
        elif sort == 'relevance':
            # Do nothing, because the results are already ordered by relevance by default
            pass


        # Log this query to the OfficerSearch log
        OfficerSearch.objects.create_officer_search(
            num_of_results=results.count(),
            parsed_search_criteria=json.dumps({
                'query_string': query_string,
                'sort': sort,
                'group': group.name if group else '',
            }),
            fdp_user=request.user,
            request=request
        )

        paginator = Paginator(results, 50)

        related_groups = (
            Grouping.objects.filter(is_law_enforcement=True)
            .filter(person_grouping__person__in=results)
            .order_by('name')
        )
        page_obj = paginator.get_page(page_number)
        return self.render_to_response({
            'title': 'Officer Search',
            'query': query_string,
            'within_group': group,
            'sort': sort,
            'page_obj': page_obj,
            'number_of_results': results.count(),
            'groups': related_groups,
        })


class OfficerDetailView(SecuredSyncDetailView):
    """ Page that displays the profile for an officer.

    """
    template_name = 'officer.html'
    model = Person
    #: Dictionary keys for the profile snapshots section
    #: Content case identifiers key in the dictionary for the profile snapshots section
    __identifiers_key = 'ids'
    #: Number of cases key in the dictionary for the profile snapshots section
    __num_cases_key = 'num_of_cases'
    #: Total for settlement amounts for cases key in the dictionary for the profile snapshots section
    __settlement_amount_total_key = 'settlement_amount_total'
    #: Dictionary keys for the profile parsed content section
    #: Attachments key in the dictionary for the profile parsed content section
    __attachments_key = 'attachments'
    #: String representing name key in the dictionary for the profile parsed content section
    __strings_key = 'strs'
    #: Links key in the dictionary for the profile parsed content section
    __links_key = 'links'

    def get_context_data(self, **kwargs):
        """ Adds the title, description and search form to the view context.

        :param kwargs:
        :return: Context for view, including title, description and search form.
        """
        context = super(OfficerDetailView, self).get_context_data(**kwargs)
        request = self.request
        user = request.user
        OfficerView.objects.create_officer_view(person=self.object, fdp_user=user, request=request)
        back_link = request.GET.get(AbstractUrlValidator.GET_PREV_URL_PARAM, None)
        context.update({
            'title': _('Officer Profile'),
            'description': _('Review an officer\'s profile, including corresponding information.'),
            'search_results_url': reverse('profiles:officer_search') if not back_link
            else '{url}?{querystring}'.format(
                url=reverse('profiles:officer_search_results'), querystring=urlunquote(back_link)
            ),
            'has_attachments': len(Person.get_officer_attachments(pk=self.object.pk, user=user)) > 0,
            'identifiers_key': self.__identifiers_key,
            'num_cases_key': self.__num_cases_key,
            'settlement_amount_total_key': self.__settlement_amount_total_key,
            'attachments_key': self.__attachments_key,
            'strings_key': self.__strings_key,
            'links_key': self.__links_key,
            'custom_text_block_profile_top': get_site_setting('custom_text_blocks-profile_page_top'),
            'custom_text_block_incidents': get_site_setting('custom_text_blocks-profile_incidents'),

        })
        return context

    @staticmethod
    def __record_relationship(rel_dict, relationship, is_accessing_object):
        """ Records a person relationship in the relationship dictionary.

        :param rel_dict: Relationship dictionary in which to record person relationship.
        :param relationship: Person relationship that should be recorded.
        :param is_accessing_object: True if object person is the other person, false if subject person is the other
        person.
        :return: Nothing.
        """
        pk = relationship.type_id
        other_person_pk = relationship.object_person_id if is_accessing_object else relationship.subject_person_id
        other_person = relationship.object_person if is_accessing_object else relationship.subject_person
        dict_key = (pk, other_person_pk)
        if dict_key not in rel_dict:
            rel_dict[dict_key] = {'person': other_person, 'relationship': relationship.type.name, 'num': 1}
        else:
            rel_dict[dict_key]['num'] += 1

    @classmethod
    def __get_dict_for_parsed_content(cls, existing_dict, str_rep, link, attachments):
        """ Retrieve a dictionary representing parsed content that will be rendered in the officer profile template.

        :param existing_dict: Existing dictionary with which to merge new data.
        :param str_rep: String representing content in the template.
        :param link: Link for content in the template.
        :param attachments: List of attachments for content.
        :return: Dictionary representing parsed content.
        """
        prev_str_reps = existing_dict.get(cls.__strings_key, [])
        prev_attachments = existing_dict.get(cls.__attachments_key, [])
        prev_links = existing_dict.get(cls.__links_key, [])
        if attachments:
            prev_attachments.extend(attachments)
        prev_links.append(link if link else None)
        prev_str_reps.append(str_rep if str_rep else _('Unnamed'))
        return {cls.__attachments_key: prev_attachments, cls.__strings_key: prev_str_reps, cls.__links_key: prev_links}

    @classmethod
    def __parse_content_for_profile(cls, content_dict, content_dict_keys, content):
        """ Parses content for the Misconduct and Content sections of the officer profile.

        :param content_dict: Existing dictionary storing already parsed contents.
        :param content_dict_keys: Existing list storing keys for already parsed content types.
        :param content: Content to parse.
        :return: Nothing.
        """
        content_case = getattr(content, 'officer_content_case', None)
        # a case is linked to this content
        if content_case:
            identifiers = content.officer_content_identifiers
            parsed_identifiers = '' if not identifiers else ', '.join([x.identifier for x in identifiers])
            content_type = _('Other case') if not content.type else content.type
            content_str = '{n}{i}'.format(
                n=content_type,
                i='' if not parsed_identifiers else ' ({i})'.format(i=parsed_identifiers)
            )
        # no case is linked to this content
        else:
            content_type = _('Other') if not content.type else content.type
            content_str = content_type
        # string representing content
        if content_str not in content_dict_keys:
            content_dict_keys.append(content_str)
        if content_str not in content_dict:
            content_dict[content_str] = {}
        content_dict[content_str] = cls.__get_dict_for_parsed_content(
            existing_dict=content_dict[content_str],
            str_rep=content_str,
            link=content.link,
            attachments=[a for a in content.officer_attachments]
        )

    @classmethod
    def __parse_content_for_snapshot(cls, content, snapshot_dict):
        """ Parses content linked to incidents for the Snapshot section of the officer's profile.

        :param content: Content to which lawsuit may be linked.
        :param snapshot_dict: Existing dictionary storing case content data for the Snapshot section.
        :return: Nothing.
        """
        content_case = getattr(content, 'officer_content_case', None)
        # a case is linked to this content
        if content_case:
            # settlement amount
            settlement_amount = content_case.settlement_amount
            # get case identifiers
            case_ids = [
                '{i}{x}'.format(
                    i=x.identifier,
                    x=' ({o}{a})'.format(
                        o=content_case.outcome,
                        a='' if not settlement_amount else ' {d}{m}'.format(d=_('$'), m=settlement_amount)
                    ) if content_case and content_case.outcome else ''
                ) for x in content.officer_content_identifiers
            ]
            # adding case into snapshot section based on type
            case_type = _('Other') if not content.type else content.type
            if case_type not in snapshot_dict:
                snapshot_dict[case_type] = {
                    cls.__identifiers_key: case_ids,
                    cls.__num_cases_key: 1,
                    cls.__settlement_amount_total_key: 0 if not settlement_amount else settlement_amount
                }
            else:
                snapshot_dict[case_type][cls.__num_cases_key] += 1
                snapshot_dict[case_type][cls.__identifiers_key].extend(case_ids)
                if settlement_amount:
                    snapshot_dict[case_type][cls.__settlement_amount_total_key] += settlement_amount

    @staticmethod
    def __parse_content_person_penalties_for_profile(content_person_penalties_list, content_person_penalty):
        """ Parses content person penalties for the Misconduct and Content sections of the officer profile.

        :param content_person_penalties_list: Existing list storing already parsed content person penalties.
        :param content_person_penalty: Content person penalty to parse.
        :return: Nothing.
        """
        penalty_received = content_person_penalty.penalty_received
        discipline_date = content_person_penalty.discipline_date
        penalty_str = '{d}{c}{r}'.format(
            d='' if not discipline_date else '{o}{d}'.format(o=_('On '), d=discipline_date.strftime('%m-%d-%Y')),
            c=', ' if discipline_date and penalty_received else '',
            r=penalty_received
        )
        # penalty already added
        if penalty_str not in content_person_penalties_list:
            content_person_penalties_list.append(penalty_str)

    def get_object(self, queryset=None):
        """ Add additional properties to retrieved officer object such as their start date in the most recent command,
        and the most recent command's name.

        :param queryset: Queryset from which officer object is retreived.
        :return: Officer object with additional properties.
        """
        obj = super(OfficerDetailView, self).get_object(queryset=queryset)
        # COMMAND
        officer_command = None
        # if the officer has commands, then cycle through and find the first active person-grouping link
        # assumes that commands are already ordered by date
        if obj.officer_commands:
            officer_command = obj.officer_commands.pop(0)
        obj.officer_command = officer_command
        # RANK
        officer_title = None
        # if the officer has titles, then cycle through and find the first person-title link
        # assumes that titles are already ordered by date
        if obj.officer_titles:
            officer_title = obj.officer_titles.pop(0)
        obj.officer_title = officer_title
        # CONTENT
        snapshot_dict = {}
        # content directly connected to misconducts

        for misconduct in obj.officer_misconducts:
            setattr(misconduct, 'allegations', [])
            setattr(misconduct, 'penalties', set())  # use a set to eliminate redundancy
            misconduct.parsed_officer_content_person_allegations = {}
            misconduct.parsed_officer_content_person_penalties = []
            misconduct.parsed_officer_contents = {}
            misconduct.parsed_officer_content_types = []
            # contents in misconduct intended for snapshot section
            for content in misconduct.incident.officer_snapshot_contents:
                self.__parse_content_for_snapshot(content=content, snapshot_dict=snapshot_dict)
            # contents in misconduct intended for misconduct section
            for content in misconduct.incident.officer_incident_contents:
                # parse for misconducts and contents sections
                self.__parse_content_for_profile(
                    content_dict=misconduct.parsed_officer_contents,
                    content_dict_keys=misconduct.parsed_officer_content_types,
                    content=content
                )

                # Aggregate allegations from the multiple content records associated with current misconduct.
                # 'officer_content_persons[0]' because there's never more than one returned from the prefetch(?).
                if content.officer_content_persons:
                    misconduct.allegations = misconduct.allegations + \
                                             content.officer_content_persons[0].officer_allegations

                for content_person in content.officer_content_persons:
                    # penalties in content person
                    for content_person_penalty in content_person.officer_penalties:
                        misconduct.penalties = set.union(misconduct.penalties, set(content_person.officer_penalties))

        # content without incidents
        for content_person in obj.officer_contents:
            content_person.parsed_officer_content_person_allegations = {}
            content_person.parsed_officer_content_person_penalties = []
            # parse for snapshots section
            self.__parse_content_for_snapshot(content=content_person.content, snapshot_dict=snapshot_dict)
            # penalties in content
            for content_person_penalty in content_person.officer_penalties:
                self.__parse_content_person_penalties_for_profile(
                    content_person_penalties_list=content_person.parsed_officer_content_person_penalties,
                    content_person_penalty=content_person_penalty
                )
        # split the snapshot section into 3 roughly even sized lists
        snapshot_dict_keys = list(snapshot_dict.keys())
        k, m = divmod(len(snapshot_dict_keys), 3)
        obj.snapshot_dict_keys = list(
            snapshot_dict_keys[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(3)
        )
        obj.officer_snapshot_dict = snapshot_dict
        # NEW RELATIONSHIPS
        setattr(obj, 'relationships', [])
        obj.relationships = obj.officer_subject_person_relationships + obj.officer_object_person_relationships

        # OLD RELATIONSHIPS
        rel_dict = {}
        for relationship in obj.officer_subject_person_relationships:
            self.__record_relationship(rel_dict=rel_dict, relationship=relationship, is_accessing_object=True)
        for relationship in obj.officer_object_person_relationships:
            self.__record_relationship(rel_dict=rel_dict, relationship=relationship, is_accessing_object=False)
        obj.officer_relationships = list(rel_dict.values())
        return obj

    def get_queryset(self):
        """ Filters the queryset for a particular user (depending on whether the user is an administrator, etc.)

        :return: Filtered queryset from which officer will be retrieved.
        """
        pk = self.kwargs['pk']
        user = self.request.user
        qs = Person.get_officer_profile_queryset(pk=pk, user=user)
        return qs


class OfficerDownloadAllFilesView(SecuredSyncView):
    """ View that allows users to download all files for a particular officer.

    """
    @staticmethod
    def __get(request, pk):
        """ Creates a ZIP archive of all attachments for an officer (only those accessible for user), and then makes it
        available for download.

        :param request: Http request object.
        :param pk: Primary key of officer for which to download all attachments.
        :return: ZIP archive of all attachments.
        """
        user = request.user
        if not pk:
            raise Exception(_('No officer was specified'))
        files_to_zip = Person.get_officer_attachments(pk=pk, user=user)
        # create ZIP archive for all attachments
        bytes_io = AbstractFileValidator.zip_files(files_to_zip=files_to_zip)
        response = HttpResponse(bytes_io, content_type='application/zip, application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="{f}"'.format(
            f='officer_{p}_all_files.zip'.format(p=pk)
        )
        return response

    def get(self, request, pk):
        """ Creates a ZIP archive of all attachments for an officer (only those accessible for user), and then makes it
        available for download.

        :param request: Http request object.
        :param pk: Primary key of officer for which to download all attachments.
        :return: ZIP archive of all attachments.
        """
        return self.__get(request=request, pk=pk)


class CommandSearchFormView(SecuredSyncFormView):
    """ Page that allows users to search for commands and corresponding information.

    """
    template_name = 'command_search.html'
    form_class = CommandSearchForm

    def __init__(self, **kwargs):
        """ Initializes the form property that will be set once the form is validated and passed to the method building
        the success URL.

        :param args:
        :param kwargs:
        """
        super(CommandSearchFormView, self).__init__(**kwargs)
        self.form = None

    @staticmethod
    def _get_search_querystring(search_text):
        """ Sets the querystring used to specify the original unparsed search criteria.

        :param search_text: A single string of search criteria entered by the user.
        :return: Querystring used to specify the original unparsed search criteria.
        """
        querystring = QueryDict('', mutable=True)
        # record original search criteria
        original_search = search_text
        # set the querystring
        querystring = AbstractUrlValidator.add_encrypted_value_to_querystring(
            querystring=querystring, key=AbstractUrlValidator.GET_ORIGINAL_PARAM, value_to_add=original_search
        )
        return querystring

    def get_success_url(self):
        """ Build link to search results containing the original unparsed search criteria as querystring GET parameter.

        :return: Link to search results for original unparsed search criteria.
        """
        search_text = self.form.cleaned_data['search']
        # process the search string entered by the user
        querystring = self._get_search_querystring(search_text=search_text)
        return '{url}?{querystring}'.format(
            url=reverse('profiles:command_search_results'),
            querystring=querystring.urlencode()
        )

    def get_context_data(self, **kwargs):
        """ Adds the title, description and search form to the view context.

        :param kwargs:
        :return: Context for view, including title, description and search form.
        """
        context = super(CommandSearchFormView, self).get_context_data(**kwargs)
        context.update({
            'title': _('Command Search'),
            'description': _('Search for commands and corresponding information.')
        })
        return context

    def form_valid(self, form):
        """ Displays paginated list of commands matching search criteria.

        Called when a valid form data is submitted via POST method.

        Returns a HttpResponse object.

        :param form: Search form that was submitted by user.
        :return:
        """
        self.form = form
        return super(CommandSearchFormView, self).form_valid(form=form)


class CommandSearchResultsListView(SecuredSyncListView):
    """ Page that allows users to browse search results displaying a filtered and paginated list of commands.

    """
    template_name = 'command_search_results.html'
    model = Grouping
    context_object_name = 'command_list'

    def __init__(self, **kwargs):
        """ Initialize the queryset count to zero, list of results to empty, the search criteria to nothing, and the
        search class that contains the searching algorithm.

        :param kwargs:
        """
        super(CommandSearchResultsListView, self).__init__(**kwargs)
        self.__count = 0
        self.__result_list = []
        self.__search_class = None

    def __parse_command_filters(self):
        """ Parses out the search criteria specified in the GET parameter that will be used to filter commands.

        :return: Nothing.
        """
        g = self.request.GET
        keys = list(g.keys())
        # retrieve a mapping from unencrypted keys to encrypted keys
        key_mapping = AbstractUrlValidator.get_key_mapping(list_of_keys=keys)
        # get original search criteria
        original_search_text = AbstractUrlValidator.get_unencrypted_value_from_querystring(
            querystring=g,
            key=AbstractUrlValidator.GET_ORIGINAL_PARAM,
            default_value='',
            key_mapping=key_mapping
        )
        # definition used for searching algorithm
        self.__search_class = GroupingProfileSearch(
            original_search_criteria=original_search_text,
            unique_table_suffix=GroupingProfileSearch.get_unique_table_suffix(user=self.request.user)
        )
        # parse the search criteria
        self.__search_class.common_parse_search_criteria()

    def __define_count_query(self):
        """ Defines the count version of the searching query.

        Sets the following properties:
         - self._count_params
         - self._sql_count_query

        :return: Nothing.
        """
        # SELECT COUNT(*) FROM ... SQL query to count groupings matching search criteria
        self._sql_count_query = """ {sql_temp_table} SELECT COUNT(DISTINCT "{grouping}"."id") {sql_from}; """.format(
            sql_temp_table=self.__search_class.temp_table_query,
            grouping=Grouping.get_db_table(),
            sql_from=self.__search_class.sql_from_query
        )
        self._count_params = self.__search_class.temp_table_params + self.__search_class.from_params

    def __define_select_query(self):
        """ Defines the select version of the searching query.

        Sets the following properties:
         - self._select_params
         - self._sql_select_query

        :return: Nothing.
        """
        # SELECT * FROM ... SQL query to retrieve groupings matching search criteria
        self._sql_select_query = """
            {sql_temp_table}
            SELECT
                A."id",
                A."name",
                MAX(A."score"),
                (
                    SELECT string_agg(ZGA."name", ', ')
                    FROM "{grouping_alias}" AS ZGA
                    WHERE ZGA."grouping_id" = A."id"
                    AND ZGA.{active_filter}
                    GROUP BY ZGA."grouping_id"
                ) AS "aliases"
            FROM
                (
                SELECT
                    "{grouping}"."id",
                    "{grouping}"."name" AS "name",
                    {sql_score}
                {sql_from}
            ) A
            GROUP BY A."id", A."name"
            ORDER BY MAX(A."score") DESC
            LIMIT {max};
        """.format(
            active_filter=Archivable.ACTIVE_FILTER,
            sql_temp_table=self.__search_class.temp_table_query,
            grouping=Grouping.get_db_table(),
            grouping_alias=GroupingAlias.get_db_table(),
            sql_from=self.__search_class.sql_from_query,
            sql_score=self.__search_class.sql_score_query,
            max=AbstractSearchValidator.MAX_WIZARD_SEARCH_RESULTS
        )
        self._select_params = self.__search_class.temp_table_params \
            + self.__search_class.score_params \
            + self.__search_class.from_params

    def __get_command_results(self):
        """ Retrieves the filtered list of commands, and the count of the commands matching the search criteria.

        Sets two properties defining the filtered and ordered list of commands matching search criteria,
        limited to the top X results.

        Property #1 is self.__count, which stores the total number of results matching the search criteria.

        Property #2 is self.__result_list, which stores the filtered and ordered list of command matching search
        criteria, limited to the top X results.

        :return: Nothing.
        """
        # user performing the search
        user = self.request.user
        # parse out the filtering criteria for commands
        self.__parse_command_filters()
        # define the body of the query
        self.__search_class.common_define_sql_query_body(user=user)
        # define the scoring for rows in the query
        self.__search_class.common_define_sql_query_score()
        # define the count version of the searching query
        self.__define_count_query()
        # define the select version of the searching query
        self.__define_select_query()
        # perform count query
        groupings_count = AbstractSql.exec_single_val_sql(
            sql_query=self._sql_count_query,
            sql_params=self._count_params
        )
        # perform select query
        groupings = Grouping.objects.raw(self._sql_select_query, self._select_params)
        self.__count = groupings_count
        self.__result_list = groupings

    def get_context_data(self, **kwargs):
        """ Adds the title, description and search form to the view context.

        :param kwargs:
        :return: Context for view, including title, description and search form.
        """
        context = super(CommandSearchResultsListView, self).get_context_data(**kwargs)
        request = self.request
        CommandSearch.objects.create_command_search(
            num_of_results=self.__count,
            parsed_search_criteria=self.__search_class.parsed_search_criteria,
            fdp_user=request.user,
            request=request
        )
        current_search_querystring = request.GET.urlencode()
        querystring = QueryDict('', mutable=True)
        querystring.update({AbstractUrlValidator.GET_PREV_URL_PARAM: urlquote(current_search_querystring)})
        context.update({
            'title': _('Command Search Results'),
            'description': _('Browse a list of commands matching the search criteria.'),
            'search': self.__search_class.parsed_search_criteria,
            'back_link_querystring': querystring.urlencode(),
            'queryset_count': self.__count,
            'max_results': AbstractSearchValidator.MAX_WIZARD_SEARCH_RESULTS,
            'has_more': (self.__count > AbstractSearchValidator.MAX_WIZARD_SEARCH_RESULTS)
        })
        return context

    def get_queryset(self):
        """ Filters the command queryset by the search criteria.

        :return: Command queryset filtered by the search criteria.
        """
        self.__get_command_results()
        return self.__result_list


class CommandDetailView(SecuredSyncDetailView):
    """ Page that displays the profile for a command.

    """
    template_name = 'command.html'
    model = Grouping
    #: Dictionary keys for the profile parsed content section
    #: Attachments key in the dictionary for the profile parsed content section
    __attachments_key = 'attachments'
    #: String representing name key in the dictionary for the profile parsed content section
    __strings_key = 'strs'
    #: Links key in the dictionary for the profile parsed content section
    __links_key = 'links'

    def get_context_data(self, **kwargs):
        """ Adds the title, description and search form to the view context.

        :param kwargs:
        :return: Context for view, including title, description and search form.
        """
        context = super(CommandDetailView, self).get_context_data(**kwargs)
        request = self.request
        user = request.user
        CommandView.objects.create_command_view(grouping=self.object, fdp_user=user, request=request)
        back_link = request.GET.get(AbstractUrlValidator.GET_PREV_URL_PARAM, None)
        context.update({
            'title': _('Command Profile'),
            'description': _('Review a command\'s profile, including corresponding information.'),
            'search_results_url': reverse('profiles:command_search') if not back_link
            else '{url}?{querystring}'.format(
                url=reverse('profiles:command_search_results'), querystring=urlunquote(back_link)
            ),
            'has_attachments': len(Grouping.get_command_attachments(pk=self.object.pk, user=user)) > 0,
            'max_person_groupings': Grouping.max_person_groupings,
            'attachments_key': self.__attachments_key,
            'strings_key': self.__strings_key,
            'links_key': self.__links_key,
            'custom_text_block_profile_top': get_site_setting('custom_text_blocks-profile_page_top'),
            'custom_text_block_incidents': get_site_setting('custom_text_blocks-profile_incidents'),
        })
        return context

    @staticmethod
    def __record_relationship(rel_dict, relationship, is_accessing_object):
        """ Records a grouping relationship in the relationship dictionary.

        :param rel_dict: Relationship dictionary in which to record grouping relationship.
        :param relationship: Grouping relationship that should be recorded.
        :param is_accessing_object: True if object grouping is the other grouping, false if subject grouping is the
        other grouping.
        :return: Nothing.
        """
        pk = relationship.type_id
        other_grouping_pk = relationship.object_grouping_id if is_accessing_object else relationship.subject_grouping_id
        other_grouping_name = \
            relationship.object_grouping.name if is_accessing_object else relationship.subject_grouping.name
        other_grouping_id = relationship.object_grouping.pk if is_accessing_object else relationship.subject_grouping.pk
        dict_key = (pk, other_grouping_pk)
        if dict_key not in rel_dict:
            rel_dict[dict_key] = {
                'grouping_id': other_grouping_id,
                'grouping': other_grouping_name,
                'relationship': relationship.type.name,
                'num': 1
            }
        else:
            rel_dict[dict_key]['num'] += 1

    @classmethod
    def __parse_content_for_profile(cls, content_dict, content_dict_keys, content):
        """ Parses content for the Misconduct sections of the command profile.

        :param content_dict: Existing dictionary storing already parsed contents.
        :param content_dict_keys: Existing list storing keys for already parsed content types.
        :param content: Content to parse.
        :return: Nothing.
        """
        content_case = getattr(content, 'command_content_case', None)
        # a case is linked to this content
        if content_case:
            identifiers = content.command_content_identifiers
            parsed_identifiers = '' if not identifiers else ', '.join([x.identifier for x in identifiers])
            content_type = _('Other case') if not content.type else content.type
            content_str = '{n}{i}'.format(
                n=content_type,
                i='' if not parsed_identifiers else ' ({i})'.format(i=parsed_identifiers)
            )
        # no case is linked to this content
        else:
            content_type = _('Other') if not content.type else content.type
            content_str = content_type
        # string representing content
        if content_str not in content_dict_keys:
            content_dict_keys.append(content_str)
        if content_str not in content_dict:
            content_dict[content_str] = {}
        content_dict[content_str] = cls.__get_dict_for_parsed_content(
            existing_dict=content_dict[content_str],
            str_rep=content_str,
            link=content.link,
            attachments=[a for a in content.command_attachments]
        )

    @classmethod
    def __get_dict_for_parsed_content(cls, existing_dict, str_rep, link, attachments):
        """ Retrieve a dictionary representing parsed content that will be rendered in the command profile template.

        :param existing_dict: Existing dictionary with which to merge new data.
        :param str_rep: String representing content in the template.
        :param link: Link for content in the template.
        :param attachments: List of attachments for content.
        :return: Dictionary representing parsed content.
        """
        prev_str_reps = existing_dict.get(cls.__strings_key, [])
        prev_attachments = existing_dict.get(cls.__attachments_key, [])
        prev_links = existing_dict.get(cls.__links_key, [])
        if attachments:
            prev_attachments.extend(attachments)
        prev_links.append(link if link else None)
        prev_str_reps.append(str_rep if str_rep else _('Unnamed'))
        return {cls.__attachments_key: prev_attachments, cls.__strings_key: prev_str_reps, cls.__links_key: prev_links}

    def get_object(self, queryset=None):
        """ Add additional properties to retrieved command object such as their relationships.

        :param queryset: Queryset from which command object is retrieved.
        :return: Command object with additional properties.
        """
        obj = super(CommandDetailView, self).get_object(queryset=queryset)
        # content directly connected to misconducts
        for misconduct in obj.command_misconducts:
            misconduct.parsed_command_contents = {}
            misconduct.parsed_command_content_types = []
            # contents in misconduct
            for content in misconduct.incident.command_contents:
                # parse for misconducts and contents sections
                self.__parse_content_for_profile(
                    content_dict=misconduct.parsed_command_contents,
                    content_dict_keys=misconduct.parsed_command_content_types,
                    content=content
                )
        # RELATIONSHIPS
        rel_dict = {}
        for relationship in obj.command_subject_grouping_relationships:
            self.__record_relationship(rel_dict=rel_dict, relationship=relationship, is_accessing_object=True)
        for relationship in obj.command_object_grouping_relationships:
            self.__record_relationship(rel_dict=rel_dict, relationship=relationship, is_accessing_object=False)
        obj.command_relationships = list(rel_dict.values())
        # counts by allegation for grouping
        obj.command_allegation_counts = self.__get_allegation_counts(grouping_id=obj.pk)
        return obj

    def __get_allegation_counts(self, grouping_id):
        """ Retrieve the total counts for each allegation that is linked to a particular grouping.

        :param grouping_id: Primary key used to identify grouping for which to retrieve allegation counts.
        :return: List of allegations, each including an "sum_of_allegation_counts" attribute.
        """
        user = self.request.user
        # confidential filter for persons
        person_confidential_filter = Person.get_confidential_filter(
            user=user,
            org_table=Person.get_db_table_for_many_to_many(many_to_many_key=Person.fdp_organizations),
            unique_alias='ZPO',
            org_obj_col='person_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=Person.get_db_table(),
        )
        # confidential filter for content
        content_confidential_filter = Content.get_confidential_filter(
            user=user,
            org_table=Content.get_db_table_for_many_to_many(many_to_many_key=Content.fdp_organizations),
            unique_alias='ZCO',
            org_obj_col='content_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=Content.get_db_table(),
        )
        # raw SQL query to retrieve allegation counts for each allegation
        raw_sql = """
            SELECT
                "{allegation}"."id" AS "id",
                "{allegation}"."name" AS "name",
                SUM("{content_person_allegation}"."allegation_count") AS "sum_of_allegation_counts"
            FROM "{person_grouping}"
            INNER JOIN "{person}"
            ON "{person_grouping}"."person_id" = "{person}"."id"
            AND {person_confidential_filter}
            AND "{person}".{active_filter}
            AND "{person}"."is_law_enforcement" = True
                INNER JOIN "{content_person}"
                ON "{person}"."id" = "{content_person}"."person_id"
                AND "{content_person}".{active_filter}
                    INNER JOIN "{content}"
                    ON "{content_person}"."content_id" = "{content}"."id"
                    AND "{content}".{active_filter}
                    AND {content_confidential_filter}
                    INNER JOIN "{content_person_allegation}"
                    ON "{content_person}"."id" = "{content_person_allegation}"."content_person_id"
                    AND "{content_person_allegation}".{active_filter}  
                        INNER JOIN "{allegation}"
                        ON "{content_person_allegation}"."allegation_id" = "{allegation}"."id"
                        AND "{allegation}".{active_filter}            
            WHERE "{person_grouping}"."grouping_id" = {grouping_id}
            AND "{person_grouping}".{active_filter}
            GROUP BY "{allegation}"."id", "{allegation}"."name"
            HAVING SUM("{content_person_allegation}"."allegation_count") > 0
            ORDER BY "{allegation}"."name" ASC
        """.format(
            person_grouping=PersonGrouping.get_db_table(),
            person=Person.get_db_table(),
            person_confidential_filter=person_confidential_filter,
            active_filter=Archivable.ACTIVE_FILTER,
            content_person=ContentPerson.get_db_table(),
            content=Content.get_db_table(),
            content_person_allegation=ContentPersonAllegation.get_db_table(),
            content_confidential_filter=content_confidential_filter,
            allegation=Allegation.get_db_table(),
            grouping_id=int(grouping_id),
        )
        allegations_qs = Allegation.objects.raw(raw_sql, [])
        return list(allegations_qs)

    def get_queryset(self):
        """ Filters the queryset for a particular user (depending on whether the user is an administrator, etc.)

        :return: Filtered queryset from which command will be retrieved.
        """
        user = self.request.user
        qs = Grouping.get_command_profile_queryset(user=user)
        return qs


class CommandDownloadAllFilesView(SecuredSyncView):
    """ View that allows users to download all files for a particular command.

    """
    @staticmethod
    def __get(request, pk):
        """ Creates a ZIP archive of all attachments for a command (only those accessible for user), and then makes it
        available for download.

        :param request: Http request object.
        :param pk: Primary key of command for which to download all attachments.
        :return: ZIP archive of all attachments.
        """
        user = request.user
        if not pk:
            raise Exception(_('No command was specified'))
        files_to_zip = Grouping.get_command_attachments(pk=pk, user=user)
        # create ZIP archive for all attachments
        bytes_io = AbstractFileValidator.zip_files(files_to_zip=files_to_zip)
        response = HttpResponse(bytes_io, content_type='application/zip, application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="{f}"'.format(
            f='command_{p}_all_files.zip'.format(p=pk)
        )
        return response

    def get(self, request, pk):
        """ Creates a ZIP archive of all attachments for a command (only those accessible for user), and then makes it
        available for download.

        :param request: Http request object.
        :param pk: Primary key of command for which to download all attachments.
        :return: ZIP archive of all attachments.
        """
        return self.__get(request=request, pk=pk)


class SiteSettingsPage(AdminSyncFormView):
    template_name = 'site_settings.html'
    form_class = SiteSettingsForm
    success_url = reverse_lazy('profiles:site_settings')
    # custom_text_blocks-profile_incidents
    def get_context_data(self, **kwargs):
        context = super(SiteSettingsPage, self).get_context_data(**kwargs)
        context.update({
            'title': _('Site settings'),
        })
        return context

    def get_initial(self):
        data = {}
        data['profile_page_top'] = get_site_setting(SiteSettingKeys.CUSTOM_TEXT_BLOCKS__PROFILE_PAGE_TOP)
        data['profile_incidents'] = get_site_setting(SiteSettingKeys.CUSTOM_TEXT_BLOCKS__PROFILE_INCIDENTS)
        data['global_footer_left'] = get_site_setting(SiteSettingKeys.CUSTOM_TEXT_BLOCKS__GLOBAL_FOOTER_LEFT)
        data['global_footer_right'] = get_site_setting(SiteSettingKeys.CUSTOM_TEXT_BLOCKS__GLOBAL_FOOTER_RIGHT)
        return data

    def form_valid(self, form):
        set_site_setting(
            'custom_text_blocks-profile_page_top',
            form.cleaned_data['profile_page_top']
        )
        set_site_setting(
            'custom_text_blocks-profile_incidents',
            form.cleaned_data['profile_incidents']
        )
        set_site_setting(
            'custom_text_blocks-global_footer_left',
            form.cleaned_data['global_footer_left']
        )
        set_site_setting(
            'custom_text_blocks-global_footer_right',
            form.cleaned_data['global_footer_right']
        )
        messages.add_message(self.request, messages.SUCCESS, 'Site settings saved')
        return super().form_valid(form)
