from django.conf import settings
from inheritable.models import Archivable, AbstractChangingSearch, AbstractSearchValidator
from core.models import Person, Incident, PersonIncident
from sourcing.models import Attachment, Content, ContentIdentifier


class IncidentChangingSearch(AbstractChangingSearch):
    """ Default definition for the searching algorithm used to identify incidents
    for the data wizard ("changing searches").

    Implements all abstract methods defined by AbstractChangingSearch.

    """

    @property
    def entity_to_count(self):
        """ Full name of entity to count when counting total search results. Can use the method get_db_table() on the
        main model being searched.

        :return: String representing full name for entity in database.
        """
        return Incident.get_db_table()

    @property
    def entity(self):
        """ Class for the main model being searched.

        :return: Class for main model.
        """
        return Incident

    def parse_search_criteria(self):
        """ Retrieves a dictionary of the parsed search criteria that was entered by the user.

        :return: Dictionary of parsed search criteria.
        """
        # make a copy of the original search text as it was entered by the user
        original_search_text = self.original_search_criteria
        # strip whitespace and convert to lowercase
        search_text = ' '.join(original_search_text.split()).lower()
        # separate out dates, without removing them from the original search text
        search_text, dates = AbstractSearchValidator.get_dates(
            search_text=search_text, remove_dates_from_search_text=False
        )
        # separate out content identifiers, removing them from the original search text
        search_text, content_identifiers = AbstractSearchValidator.get_content_identifiers(
            search_text=search_text,
            remove_identifiers_from_search_text=True
        )
        # split the search terms into individual terms
        terms = AbstractSearchValidator.get_terms(search_text=search_text)
        # find all ordered adjacent pairings of search terms
        pairings = AbstractSearchValidator.get_adjacent_pairings(search_text=search_text, handle_initials=True)
        return {
            self._original_key: original_search_text,
            self._terms_key: terms,
            self._adjacent_pairings_key: pairings,
            self._content_identifiers_key: content_identifiers,
            self._dates_key: dates
        }

    def define_sql_query_body(self, user):
        """ Defines the body of the SQL query, and optionally any preceding temporary tables, used to retrieve incidents
        matching the parsed search criteria.

        :param user: User performing the search.
        :return: A tuple containing four elements in the following order:
            0: SQL statement with optional temporary table definitions
            1: SQL statement with FROM and WHERE portions of main query
            2: Parameters for SQL statement for optional temporary table definitions
            3: Parameters for SQL statement for FROM and WHERE portions of main query
        """
        parsed_search_criteria = self.parsed_search_criteria
        pairings = parsed_search_criteria[self._adjacent_pairings_key]
        terms = parsed_search_criteria[self._terms_key]
        dates = parsed_search_criteria[self._dates_key]
        identifiers = parsed_search_criteria[self._content_identifiers_key]
        num_of_terms = len(terms)
        num_of_identifiers = len(identifiers)
        # build the query to check against incident dates
        incident_dates_check = AbstractSearchValidator.get_date_components_check_sql(
            dates_to_check=dates,
            table='{incident}'.format(incident=Incident.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # build the query to check against incident description
        incident_description_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_terms,
            lhs_of_check='"{incident}"."description"'.format(incident=Incident.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating incident description score
        incident_description_whens = '' if pairings else AbstractSearchValidator.EMPTY_WHEN_INT
        for pairing in pairings:
            incident_description_whens += """
                WHEN "{incident}"."description" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                incident=Incident.get_db_table(),
                score=self._get_primary_name_score(name=pairing)
            )
        # build the query to check against person names
        person_name_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_terms,
            lhs_of_check='"{person}"."name"'.format(person=Person.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating person name score
        person_name_whens = '' if pairings else AbstractSearchValidator.EMPTY_WHEN_INT
        for pairing in pairings:
            person_name_whens += """
                WHEN "{person}"."name" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                person=Person.get_db_table(),
                score=self._get_primary_name_score(name=pairing)
            )
        # build the query to check against attachment names
        attachment_name_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_terms,
            lhs_of_check='"{attachment}"."name"'.format(attachment=Attachment.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating attachment name score
        attachment_name_whens = '' if pairings else AbstractSearchValidator.EMPTY_WHEN_INT
        for pairing in pairings:
            attachment_name_whens += """
                WHEN "{attachment}"."name" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                attachment=Attachment.get_db_table(),
                score=self._get_secondary_name_score(name=pairing)
            )
        # build the query to check against content names
        content_name_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_terms,
            lhs_of_check='"{content}"."name"'.format(content=Content.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating content name score
        content_name_whens = '' if pairings else AbstractSearchValidator.EMPTY_WHEN_INT
        for pairing in pairings:
            content_name_whens += """
                WHEN "{content}"."name" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                content=Content.get_db_table(),
                score=self._get_secondary_name_score(name=pairing)
            )
        # build the query to check against content identifiers
        content_identifier_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_identifiers,
            lhs_of_check='"{content_identifier}"."identifier"'.format(
                content_identifier=ContentIdentifier.get_db_table()
            ),
            is_and=False,
            fail_on_default=True
        )
        # calculating content identifier score
        content_identifier_whens = '' if identifiers else AbstractSearchValidator.EMPTY_WHEN_INT
        for identifier in identifiers:
            content_identifier_whens += """
                WHEN "{content_identifier}"."identifier" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                content_identifier=ContentIdentifier.get_db_table(),
                score=self._get_secondary_identifier_score(identifier=identifier)
            )
        # confidential filter for incidents
        incident_confidential_filter = Incident.get_confidential_filter(
            user=user,
            org_table=Incident.get_db_table_for_many_to_many(many_to_many_key=Incident.fdp_organizations),
            unique_alias='ZICO',
            org_obj_col='incident_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=Incident.get_db_table(),
        )
        # confidential filter for persons
        person_confidential_filter = Person.get_confidential_filter(
            user=user,
            org_table=Person.get_db_table_for_many_to_many(many_to_many_key=Person.fdp_organizations),
            unique_alias='ZPCO',
            org_obj_col='person_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=Person.get_db_table(),
        )
        # confidential filter for content
        content_confidential_filter = Content.get_confidential_filter(
            user=user,
            org_table=Content.get_db_table_for_many_to_many(many_to_many_key=Content.fdp_organizations),
            unique_alias='ZCCO',
            org_obj_col='content_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=Content.get_db_table(),
        )
        # confidential filter for content identifier
        content_identifier_confidential_filter = ContentIdentifier.get_confidential_filter(
            user=user,
            org_table=ContentIdentifier.get_db_table_for_many_to_many(
                many_to_many_key=ContentIdentifier.fdp_organizations
            ),
            unique_alias='ZCICO',
            org_obj_col='contentidentifier_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=ContentIdentifier.get_db_table(),
        )
        # confidential filter for attachment
        attachment_confidential_filter = Attachment.get_confidential_filter(
            user=user,
            org_table=Attachment.get_db_table_for_many_to_many(many_to_many_key=Attachment.fdp_organizations),
            unique_alias='ZACO',
            org_obj_col='attachment_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=Attachment.get_db_table(),
        )
        # FROM portion of the SQL query to retrieve content matching search criteria
        prefix = self.temp_table_prefix
        suffix = self.unique_table_suffix
        sql_from_query = """
            FROM "{incident}"
                LEFT JOIN "{tmp_incident_score}"
                ON "{incident}"."id" = "{tmp_incident_score}"."id"            
                LEFT JOIN LATERAL (
                    SELECT COALESCE("{tmp_person_score}"."score",0) AS "score"
                    FROM "{person_incident}"
                    INNER JOIN "{tmp_person_score}"
                    ON "{person_incident}"."person_id" = "{tmp_person_score}"."id"                                                                
                    WHERE "{incident}"."id" = "{person_incident}"."incident_id"
                    AND "{person_incident}".{active_filter}
                ) ZP
                on true
                LEFT JOIN LATERAL (
                    SELECT COALESCE("{tmp_content_score}"."score",0) AS "score"
                    FROM "{content_incident}"
                    INNER JOIN "{tmp_content_score}"
                    ON "{content_incident}"."content_id" = "{tmp_content_score}"."id"                                                                
                    WHERE "{incident}"."id" = "{content_incident}"."incident_id"
                ) ZC
                on true
            WHERE "{incident}".{active_filter}
            AND ({incident_confidential_filter})
            AND ( 
                   ("{tmp_incident_score}"."id" IS NOT NULL)
                OR (ZP."score" > 0)
                OR (ZC."score" > 0)
                OR ({incident_dates_check})
                )
        """.format(
            tmp_incident_score=self._tmp_incident_score.format(prefix=prefix, suffix=suffix),
            tmp_person_score=self._tmp_person_score.format(prefix=prefix, suffix=suffix),
            tmp_content_score=self._tmp_content_score.format(prefix=prefix, suffix=suffix),
            incident=Incident.get_db_table(),
            person_incident=PersonIncident.get_db_table(),
            content_incident=Content.get_db_table_for_many_to_many(many_to_many_key=Content.incidents),
            active_filter=Archivable.ACTIVE_FILTER,
            incident_confidential_filter=incident_confidential_filter,
            incident_dates_check=incident_dates_check
        )
        # SQL FROM PARAMS
        from_params = []
        # Temporary Table portion of the SQL query to retrieve content matching search criteria
        temp_table_query = """
        {create_temp_table_sql} "{tmp_incident_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_incident_score}" ("id", "score")
        SELECT "id" AS "id", CASE {incident_description_whens} ELSE 0 END AS "score"
        FROM "{incident}" 
        WHERE ({incident_confidential_filter}) 
        AND ("{incident}".{active_filter}) 
        AND ({incident_description_check});        
        
        {create_temp_table_sql} "{tmp_person_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_person_score}" ("id", "score")
        SELECT "id" AS "id", CASE {person_name_whens} ELSE 0 END AS "score"
        FROM "{person}" 
        WHERE ({person_confidential_filter}) 
        AND ("{person}".{active_filter}) 
        AND ({person_name_check});

        {create_temp_table_sql} "{tmp_attachment_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_attachment_score}" ("id", "score")
        SELECT "{content}"."id" AS "id", CASE {attachment_name_whens} ELSE 0 END AS "score"
        FROM "{attachment}"
        INNER JOIN "{content_attachment}"
        ON "{attachment}"."id" = "{content_attachment}"."attachment_id"
        INNER JOIN "{content}"
        ON "{content_attachment}"."content_id" = "{content}"."id"
        AND ({content_confidential_filter})        
        WHERE ({attachment_confidential_filter}) 
        AND ("{attachment}".{active_filter}) 
        AND ({attachment_name_check});

        {create_temp_table_sql} "{tmp_content_identifier_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_content_identifier_score}" ("id", "score")
        SELECT "content_id" AS "id", CASE {content_identifier_whens} ELSE 0 END AS "score"
        FROM "{content_identifier}" 
        WHERE ({content_identifier_confidential_filter}) 
        AND ("{content_identifier}".{active_filter}) 
        AND ({content_identifier_check});
        
        {create_temp_table_sql} "{tmp_content_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_content_score}" ("id", "score")
        SELECT 
            "{content}"."id" AS "id", 
            CASE {content_name_whens} ELSE 0 END 
                + COALESCE("{tmp_content_identifier_score}"."score", 0) + 
                + COALESCE("{tmp_attachment_score}"."score", 0)
            AS "score"
        FROM "{content}"
            LEFT JOIN "{tmp_content_identifier_score}"
            ON "{content}"."id" = "{tmp_content_identifier_score}"."id"
            LEFT JOIN "{tmp_attachment_score}"
            ON "{content}"."id" = "{tmp_attachment_score}"."id"
        WHERE ({content_confidential_filter})
        AND ("{content}".{active_filter}) 
        AND (
               ({content_name_check})
            OR ("{tmp_content_identifier_score}"."id" IS NOT NULL)
            OR ("{tmp_attachment_score}"."id" IS NOT NULL)
        );        

        """.format(
            incident_confidential_filter=incident_confidential_filter,
            content_confidential_filter=content_confidential_filter,
            content_identifier_confidential_filter=content_identifier_confidential_filter,
            attachment_confidential_filter=attachment_confidential_filter,
            person_confidential_filter=person_confidential_filter,
            active_filter=Archivable.ACTIVE_FILTER,
            create_temp_table_sql=self.create_temp_table_sql,
            on_commit_temp_table_sql=self.on_commit_temp_table_sql,
            tmp_incident_score=self._tmp_incident_score.format(prefix=prefix, suffix=suffix),
            tmp_person_score=self._tmp_person_score.format(prefix=prefix, suffix=suffix),
            tmp_content_score=self._tmp_content_score.format(prefix=prefix, suffix=suffix),
            tmp_content_identifier_score=self._tmp_content_identifier_score.format(prefix=prefix, suffix=suffix),
            tmp_attachment_score=self._tmp_attachment_score.format(prefix=prefix, suffix=suffix),
            content=Content.get_db_table(),
            incident=Incident.get_db_table(),
            attachment=Attachment.get_db_table(),
            content_identifier=ContentIdentifier.get_db_table(),
            person=Person.get_db_table(),
            content_attachment=Content.get_db_table_for_many_to_many(many_to_many_key=Content.attachments),
            incident_description_whens=incident_description_whens,
            incident_description_check=incident_description_check,
            content_name_whens=content_name_whens,
            content_name_check=content_name_check,
            attachment_name_whens=attachment_name_whens,
            attachment_name_check=attachment_name_check,
            person_name_whens=person_name_whens,
            person_name_check=person_name_check,
            content_identifier_whens=content_identifier_whens,
            content_identifier_check=content_identifier_check,
        )
        # TEMP TABLE PARAMS
        # incident_description_whens                pairings
        # incident_description_check                terms
        # person_name_whens                         pairings
        # person_name_check                         terms
        # attachment_name_whens                     pairings
        # attachment_name_check                     terms
        # content_identifier_whens                  identifiers
        # content_identifier_check                  identifiers
        # content_name_whens                        pairings
        # content_name_check                        terms
        temp_table_params = pairings + terms + pairings + terms + pairings + terms + \
            identifiers + identifiers + pairings + terms
        return temp_table_query, sql_from_query, temp_table_params, from_params

    def define_sql_query_score(self):
        """ Defines the scoring portion of the SQL query used to retrieve incidents matching the parsed search criteria.

        :return: A tuple containing two elements in the following order:
            0: SQL statement with definition for scoring column in main query
            1: Parameters for SQL statement for definition for scoring column in main query

        """
        parsed_search_criteria = self.parsed_search_criteria
        dates = parsed_search_criteria[self._dates_key]
        # score the row according to matching criteria
        prefix = self.temp_table_prefix
        suffix = self.unique_table_suffix
        # build the query to check against incident dates
        incident_dates_check = AbstractSearchValidator.get_date_components_check_sql(
            dates_to_check=dates,
            table='{incident}'.format(incident=Incident.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        sql_score_query = """
            CASE WHEN {incident_dates_check} THEN {incident_dates_score} ELSE 0 END +
            COALESCE("{tmp_incident_score}"."score", 0) +
            COALESCE(ZP."score", 0) +
            COALESCE(ZC."score", 0)
            AS "score" """.format(
            tmp_incident_score=self._tmp_incident_score.format(prefix=prefix, suffix=suffix),
            incident_dates_score=self._get_primary_date_score(),
            incident_dates_check=incident_dates_check
        )
        # PARAMS
        score_params = []
        return sql_score_query, score_params

    class Meta:
        managed = False
