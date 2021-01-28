from django.conf import settings
from inheritable.models import Archivable, AbstractProfileSearch, AbstractSearchValidator
from core.models import Person, PersonAlias, PersonIdentifier, PersonTitle, PersonGrouping, Grouping, GroupingAlias
from supporting.models import County, Title


class PersonProfileSearch(AbstractProfileSearch):
    """ Default definition for the searching algorithm used to identify person profiles.

    Implements all abstract methods defined by AbstractProfileSearch.

    """
    def parse_search_criteria(self):
        """ Retrieves a dictionary of the parsed search criteria that was entered by the user.

        :return: Dictionary of parsed search criteria.
        """
        # make a copy of the original search text as it was entered by the user
        original_search_text = self.original_search_criteria
        # strip whitespace and convert to lowercase
        search_text = ' '.join(original_search_text.split()).lower()
        # separate out person identifiers, removing them from the original search text
        search_text, person_identifiers = AbstractSearchValidator.get_person_identifiers(
            search_text=search_text,
            remove_identifiers_from_search_text=True
        )
        # retrieve counties
        all_counties = County.get_as_list(fields=['name'])
        counties = [c.pk for c in all_counties if c.name.lower() in search_text]
        # retrieve titles
        all_titles = Title.get_as_list(fields=['name'])
        titles = [r.pk for r in all_titles if r.name.lower() in search_text]
        # split the search terms into individual terms
        terms = AbstractSearchValidator.get_terms(search_text=search_text)
        # add versions of all terms without their apostrophes, e.g. O'Brien becomes Brien
        apostrophe_free_terms = AbstractSearchValidator.get_apostrophe_free_terms(terms=terms)
        terms.extend(apostrophe_free_terms)
        # find all ordered adjacent pairings of search terms
        pairings = AbstractSearchValidator.get_adjacent_pairings(search_text=search_text, handle_initials=True)
        return {
            self._original_key: original_search_text,
            self._terms_key: terms,
            self._adjacent_pairings_key: pairings,
            self._titles_key: titles,
            self._person_identifiers_key: person_identifiers,
            self._counties_key: counties
        }

    def define_sql_query_body(self, user):
        """ Defines the body of the SQL query, and optionally any preceding temporary tables, used to retrieve persons
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
        titles = parsed_search_criteria[self._titles_key]
        counties = parsed_search_criteria[self._counties_key]
        identifiers = parsed_search_criteria[self._person_identifiers_key]
        num_of_terms = len(terms)
        num_of_identifiers = len(identifiers)
        # build the query to check against titles
        titles_check = AbstractSearchValidator.get_in_ids_list_check_sql(
            list_of_ids=titles,
            extra_check=None,
            lhs_of_check='"{person_title}"."title_id"'.format(person_title=PersonTitle.get_db_table()),
            fail_on_default=True
        )
        # build the query to check against counties
        counties_check = AbstractSearchValidator.get_in_ids_list_check_sql(
            list_of_ids=counties,
            extra_check=None,
            lhs_of_check='"{grouping_county}"."county_id"'.format(
                grouping_county=Grouping.get_db_table_for_many_to_many(many_to_many_key=Grouping.counties)
            ),
            fail_on_default=True
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
        # build the query to check against person alias names
        person_alias_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_terms,
            lhs_of_check='"{person_alias}"."name"'.format(person_alias=PersonAlias.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating person alias score
        person_alias_whens = '' if pairings else AbstractSearchValidator.EMPTY_WHEN_INT
        for pairing in pairings:
            person_alias_whens += """
                WHEN "{person_alias}"."name" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                person_alias=PersonAlias.get_db_table(),
                score=self._get_primary_alias_score(alias=pairing)
            )
        # build the query to check against grouping names
        grouping_name_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_terms,
            lhs_of_check='"{grouping}"."name"'.format(grouping=Grouping.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating grouping name score
        grouping_name_whens = '' if pairings else AbstractSearchValidator.EMPTY_WHEN_INT
        for pairing in pairings:
            grouping_name_whens += """
                WHEN "{grouping}"."name" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                grouping=Grouping.get_db_table(),
                score=self._get_secondary_name_score(name=pairing)
            )
        # build the query to check against grouping alias names
        grouping_alias_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_terms,
            lhs_of_check='"{grouping_alias}"."name"'.format(grouping_alias=GroupingAlias.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating grouping alias score
        grouping_alias_whens = '' if pairings else AbstractSearchValidator.EMPTY_WHEN_INT
        for pairing in pairings:
            grouping_alias_whens += """
                WHEN "{grouping_alias}"."name" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                grouping_alias=GroupingAlias.get_db_table(),
                score=self._get_secondary_alias_score(alias=pairing)
            )
        # build the query to check against person identifiers
        person_identifier_check = AbstractSearchValidator.get_partial_check_sql(
            num_of_checks=num_of_identifiers,
            lhs_of_check='"{person_identifier}"."identifier"'.format(person_identifier=PersonIdentifier.get_db_table()),
            is_and=False,
            fail_on_default=True
        )
        # calculating person identifier score
        person_identifier_whens = '' if identifiers else AbstractSearchValidator.EMPTY_WHEN_INT
        for identifier in identifiers:
            person_identifier_whens += """
                WHEN "{person_identifier}"."identifier" ILIKE \'%%\' || %s || \'%%\' THEN {score}
            """.format(
                person_identifier=PersonIdentifier.get_db_table(),
                score=self._get_primary_identifier_score(identifier=identifier)
            )
        # confidential filter for persons
        confidential_filter = Person.get_confidential_filter(
            user=user,
            org_table=Person.get_db_table_for_many_to_many(many_to_many_key=Person.fdp_organizations),
            unique_alias='ZPCO',
            org_obj_col='person_id',
            obj_col='id',
            org_org_col='{p}organization_id'.format(p=settings.DB_PREFIX.lower().strip('_')),
            prefix=Person.get_db_table(),
        )
        # FROM portion of the SQL query to retrieve persons matching search criteria
        prefix = self.temp_table_prefix
        suffix = self.unique_table_suffix
        sql_from_query = """
            FROM "{person}"
                LEFT JOIN "{tmp_person_score}"
                ON "{person}"."id" = "{tmp_person_score}"."id"            
                LEFT JOIN "{tmp_person_alias_score}"
                ON "{person}"."id" = "{tmp_person_alias_score}"."id"                    
                LEFT JOIN "{tmp_person_identifier_score}"
                ON "{person}"."id" = "{tmp_person_identifier_score}"."id"                            
                LEFT JOIN LATERAL (
                    SELECT COALESCE("{tmp_grouping_score}"."score",0) AS "score"
                    FROM "{person_grouping}"
                    INNER JOIN "{tmp_grouping_score}"
                    ON "{person_grouping}"."grouping_id" = "{tmp_grouping_score}"."id"                                                                
                    WHERE "{person}"."id" = "{person_grouping}"."person_id"
                    AND "{person_grouping}".{active_filter}
                ) ZPG
                ON true                
                LEFT JOIN "{person_title}"
                ON "{person}"."id" = "{person_title}"."person_id"
                AND ({titles_check})                     
                AND "{person_title}".{active_filter}
            WHERE "{person}"."is_law_enforcement" = True 
            AND "{person}".{active_filter}
            AND ({confidential_filter})
            AND ( 
                   ("{tmp_person_score}"."id" IS NOT NULL)
                OR ("{tmp_person_alias_score}"."id" IS NOT NULL)
                OR ("{tmp_person_identifier_score}"."id" IS NOT NULL)
                OR (ZPG."score" > 0)
                OR ("{person_title}"."id" IS NOT NULL)                
                )
        """.format(
            tmp_person_score=self._tmp_person_score.format(prefix=prefix, suffix=suffix),
            tmp_person_identifier_score=self._tmp_person_identifier_score.format(prefix=prefix, suffix=suffix),
            tmp_grouping_score=self._tmp_grouping_score.format(prefix=prefix, suffix=suffix),
            tmp_person_alias_score=self._tmp_person_alias_score.format(prefix=prefix, suffix=suffix),
            person=Person.get_db_table(),
            person_alias=PersonAlias.get_db_table(),
            person_identifier=PersonIdentifier.get_db_table(),
            person_grouping=PersonGrouping.get_db_table(),
            person_title=PersonTitle.get_db_table(),
            grouping=Grouping.get_db_table(),
            active_filter=Archivable.ACTIVE_FILTER,
            confidential_filter=confidential_filter,
            titles_check=titles_check,
        )
        # SQL FROM PARAMS
        from_params = []
        # Temporary Table portion of the SQL query to retrieve persons matching search criteria
        temp_table_query = """
        {create_temp_table_sql} "{tmp_person_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_person_score}" ("id", "score")
        SELECT "id" AS "id", CASE {person_name_whens} ELSE 0 END AS "score"
        FROM "{person}" WHERE ({confidential_filter}) AND ("{person}".{active_filter}) AND ({person_name_check});            

        {create_temp_table_sql} "{tmp_person_alias_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_person_alias_score}" ("id", "score")
        SELECT "person_id" AS "id", CASE {person_alias_whens} ELSE 0 END AS "score"
        FROM "{person_alias}" WHERE ("{person_alias}".{active_filter}) AND ({person_alias_check});

        {create_temp_table_sql} "{tmp_person_identifier_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_person_identifier_score}" ("id", "score")
        SELECT "person_id" AS "id", CASE {person_identifier_whens} ELSE 0 END AS "score"
        FROM "{person_identifier}" WHERE ("{person_identifier}".{active_filter}) AND ({person_identifier_check});            
        
        {create_temp_table_sql} "{tmp_grouping_alias_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_grouping_alias_score}" ("id", "score")
        SELECT "grouping_id" AS "id", CASE {grouping_alias_whens} ELSE 0 END AS "score"
        FROM "{grouping_alias}" WHERE ("{grouping_alias}".{active_filter}) AND ({grouping_alias_check});

        {create_temp_table_sql} "{tmp_grouping_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_grouping_score}" ("id", "score")
        SELECT 
            "{grouping}"."id" AS "id", 
            CASE {grouping_name_whens} ELSE 0 END 
                + COALESCE("{tmp_grouping_alias_score}"."score", 0) + 
                + CASE WHEN "{grouping_county}"."id" IS NOT NULL THEN {county_score} ELSE 0 END
            AS "score"
        FROM "{grouping}"
            LEFT JOIN "{tmp_grouping_alias_score}"
            ON "{grouping}"."id" = "{tmp_grouping_alias_score}"."id"
            LEFT JOIN "{grouping_county}"
            ON "{grouping}"."id" = "{grouping_county}"."grouping_id"
            AND ({counties_check})
        WHERE ("{grouping}".{active_filter}) 
        AND (
               ({grouping_name_check})
            OR ("{tmp_grouping_alias_score}"."id" IS NOT NULL)
            OR ("{grouping_county}"."id" IS NOT NULL)
        );                                                  
        """.format(
            confidential_filter=confidential_filter,
            active_filter=Archivable.ACTIVE_FILTER,
            create_temp_table_sql=self.create_temp_table_sql,
            on_commit_temp_table_sql=self.on_commit_temp_table_sql,
            tmp_person_score=self._tmp_person_score.format(prefix=prefix, suffix=suffix),
            tmp_person_identifier_score=self._tmp_person_identifier_score.format(prefix=prefix, suffix=suffix),
            tmp_grouping_score=self._tmp_grouping_score.format(prefix=prefix, suffix=suffix),
            tmp_grouping_alias_score=self._tmp_grouping_alias_score.format(prefix=prefix, suffix=suffix),
            tmp_person_alias_score=self._tmp_person_alias_score.format(prefix=prefix, suffix=suffix),
            person=Person.get_db_table(),
            person_identifier=PersonIdentifier.get_db_table(),
            person_alias=PersonAlias.get_db_table(),
            grouping=Grouping.get_db_table(),
            grouping_alias=GroupingAlias.get_db_table(),
            grouping_county=Grouping.get_db_table_for_many_to_many(many_to_many_key=Grouping.counties),
            person_name_whens=person_name_whens,
            person_name_check=person_name_check,
            person_alias_whens=person_alias_whens,
            person_alias_check=person_alias_check,
            person_identifier_whens=person_identifier_whens,
            person_identifier_check=person_identifier_check,
            grouping_name_whens=grouping_name_whens,
            grouping_name_check=grouping_name_check,
            grouping_alias_whens=grouping_alias_whens,
            grouping_alias_check=grouping_alias_check,
            counties_check=counties_check,
            county_score=self._get_secondary_lookup_score()
        )
        # TEMP TABLE PARAMS
        # person_name_whens                         pairings
        # person_name_checks                        terms
        # person_alias_whens                        pairings
        # person_alias_checks                       terms
        # person_identifier_whens                   identifiers
        # person_identifier_checks                  identifiers
        # grouping_alias_whens                      pairings
        # grouping_alias_checks                     terms
        # grouping_name_whens                       pairings
        # grouping_name_checks                      terms
        temp_table_params = pairings + terms + pairings + terms + \
            identifiers + identifiers + \
            pairings + terms + pairings + terms
        return temp_table_query, sql_from_query, temp_table_params, from_params

    def define_sql_query_score(self):
        """ Defines the scoring portion of the SQL query used to retrieve persons matching the parsed search criteria.

        :return: A tuple containing two elements in the following order:
            0: SQL statement with definition for scoring column in main query
            1: Parameters for SQL statement for definition for scoring column in main query

        """
        # score the row according to matching criteria
        prefix = self.temp_table_prefix
        suffix = self.unique_table_suffix
        sql_score_query = """
            COALESCE("{tmp_person_score}"."score", 0) +
            COALESCE("{tmp_person_alias_score}"."score", 0) +
            COALESCE("{tmp_person_identifier_score}"."score", 0) +
            COALESCE(ZPG."score", 0)
            AS "score" """.format(
            tmp_person_score=self._tmp_person_score.format(prefix=prefix, suffix=suffix),
            tmp_person_identifier_score=self._tmp_person_identifier_score.format(prefix=prefix, suffix=suffix),
            tmp_person_alias_score=self._tmp_person_alias_score.format(prefix=prefix, suffix=suffix),
        )
        # PARAMS
        score_params = []
        return sql_score_query, score_params

    class Meta:
        managed = False
