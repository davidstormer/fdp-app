from inheritable.models import Archivable, AbstractProfileSearch, AbstractSearchValidator
from core.models import Person, PersonAlias, Grouping, GroupingAlias


class GroupingProfileSearch(AbstractProfileSearch):
    """ Default definition for the searching algorithm used to identify grouping profiles.

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
        # split the search terms into individual terms
        terms = AbstractSearchValidator.get_terms(search_text=search_text)
        # find all ordered adjacent pairings of search terms
        pairings = AbstractSearchValidator.get_adjacent_pairings(search_text=search_text, handle_initials=True)
        return {
            self._original_key: original_search_text,
            self._terms_key: terms,
            self._adjacent_pairings_key: pairings
        }

    def define_sql_query_body(self, user):
        """ Defines the body of the SQL query, and optionally any preceding temporary tables, used to retrieve groupings
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
        num_of_terms = len(terms)
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
                score=self._get_primary_name_score(name=pairing)
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
                score=self._get_primary_alias_score(alias=pairing)
            )
        # FROM portion of the SQL query to retrieve groupings matching search criteria
        prefix = self.temp_table_prefix
        suffix = self.unique_table_suffix
        sql_from_query = """
            FROM "{grouping}"
                LEFT JOIN "{tmp_grouping_score}"
                ON "{grouping}"."id" = "{tmp_grouping_score}"."id"            
                LEFT JOIN "{tmp_grouping_alias_score}"
                ON "{grouping}"."id" = "{tmp_grouping_alias_score}"."id"                    
            WHERE "{grouping}"."is_law_enforcement" = True
            AND "{grouping}".{active_filter}             
            AND ( 
                   ("{tmp_grouping_score}"."id" IS NOT NULL)
                OR ("{tmp_grouping_alias_score}"."id" IS NOT NULL)                
                )
        """.format(
            tmp_grouping_score=self._tmp_grouping_score.format(prefix=prefix, suffix=suffix),
            tmp_grouping_alias_score=self._tmp_grouping_alias_score.format(prefix=prefix, suffix=suffix),
            grouping=Grouping.get_db_table(),
            person=Person.get_db_table(),
            person_alias=PersonAlias.get_db_table(),
            active_filter=Archivable.ACTIVE_FILTER
        )
        # SQL FROM PARAMS
        from_params = []
        # Temporary Table portion of the SQL query to retrieve groupings matching search criteria
        temp_table_query = """
        {create_temp_table_sql} "{tmp_grouping_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_grouping_score}" ("id", "score")
        SELECT
            "id" AS "id",
            CASE {grouping_name_whens} ELSE 0 END 
            AS "score"
        FROM "{grouping}" 
        WHERE ("{grouping}".{active_filter}) 
        AND ({grouping_name_check});            

        {create_temp_table_sql} "{tmp_grouping_alias_score}" ("id" INTEGER NOT NULL, "score" INTEGER NOT NULL)
        {on_commit_temp_table_sql} INSERT INTO "{tmp_grouping_alias_score}" ("id", "score")
        SELECT "grouping_id" AS "id", CASE {grouping_alias_whens} ELSE 0 END AS "score"
        FROM "{grouping_alias}" WHERE ("{grouping_alias}".{active_filter}) AND ({grouping_alias_check});
        """.format(
            active_filter=Archivable.ACTIVE_FILTER,
            create_temp_table_sql=self.create_temp_table_sql,
            on_commit_temp_table_sql=self.on_commit_temp_table_sql,
            tmp_grouping_score=self._tmp_grouping_score.format(prefix=prefix, suffix=suffix),
            tmp_grouping_alias_score=self._tmp_grouping_alias_score.format(prefix=prefix, suffix=suffix),
            grouping=Grouping.get_db_table(),
            grouping_alias=GroupingAlias.get_db_table(),
            grouping_name_whens=grouping_name_whens,
            grouping_name_check=grouping_name_check,
            grouping_alias_whens=grouping_alias_whens,
            grouping_alias_check=grouping_alias_check,
        )
        # TEMP TABLE PARAMS
        # grouping_name_whens                       pairings
        # grouping_name_checks                      terms
        # grouping_alias_whens                      pairings
        # grouping_alias_checks                     terms
        temp_table_params = pairings + terms + pairings + terms
        return temp_table_query, sql_from_query, temp_table_params, from_params

    def define_sql_query_score(self):
        """ Defines the scoring portion of the SQL query used to retrieve groupings matching the parsed search criteria.

        :return: A tuple containing two elements in the following order:
            0: SQL statement with definition for scoring column in main query
            1: Parameters for SQL statement for definition for scoring column in main query

        """
        # score the row according to matching criteria
        prefix = self.temp_table_prefix
        suffix = self.unique_table_suffix
        sql_score_query = """
            COALESCE("{tmp_grouping_score}"."score", 0) +
            COALESCE("{tmp_grouping_alias_score}"."score", 0)
            AS "score" """.format(
            tmp_grouping_score=self._tmp_grouping_score.format(prefix=prefix, suffix=suffix),
            tmp_grouping_alias_score=self._tmp_grouping_alias_score.format(prefix=prefix, suffix=suffix),
        )
        # PARAMS
        score_params = []
        return sql_score_query, score_params

    class Meta:
        managed = False
