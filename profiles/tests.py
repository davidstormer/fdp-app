from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from inheritable.tests import AbstractTestCase
from fdpuser.models import FdpOrganization, FdpUser
from core.models import Person, PersonIncident, Incident, PersonRelationship, Grouping, PersonGrouping, GroupingIncident
from sourcing.models import Attachment, Content, ContentPerson, ContentIdentifier, ContentCase
from supporting.models import PersonRelationshipType, ContentIdentifierType
from os.path import splitext


class ProfileTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test for Officer Profile Search Results and Profile Views for all permutations of user roles, confidentiality
    levels and relevant models:
            (A) Person has different levels of confidentiality
            (B) Incident has different levels of confidentiality
            (C) Content has different levels of confidentiality
            (D) Attachment has different levels of confidentiality
            (E) Content Identifier has different levels of confidentiality

    (2) Test for Command Profile Views for all permutations of user roles, confidentiality
    levels and relevant models:
            (A) Person has different levels of confidentiality
            (B) Incident has different levels of confidentiality
            (C) Content has different levels of confidentiality
            (D) Attachment has different levels of confidentiality
            (E) Content Identifier has different levels of confidentiality

    """
    #: Dictionary that can be expanded into keyword arguments to define officer profile searching URLs.
    _officer_profile_search_url_dict = {
        'search_url': reverse('profiles:officer_search'),
        'search_results_url': reverse('profiles:officer_search_results')
    }

    #: View name parameter for reverse(...) when generating officer profile URL.
    _officer_profile_view_name = 'profiles:officer'

    #: Dictionary that can be expanded into keyword arguments to define command profile searching URLs.
    _command_profile_search_url_dict = {
        'search_url': reverse('profiles:command_search'),
        'search_results_url': reverse('profiles:command_search_results')
    }

    #: View name parameter for reverse(...) when generating command profile URL.
    _command_profile_view_name = 'profiles:command'

    def __print_profile_download_attachments_with_right_org(self, user_role, view_txt):
        """ Prints into the console the start of a profile download attachments test with matching FDP
        organization.

        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(
            _('\nStarting {v} profile download attachments sub-test for {u} with matching FDP organization'.format(
                u=user_role[self._label],
                v=view_txt
            ))
        )

    def __print_profile_download_attachments_with_wrong_org(self, user_role, view_txt):
        """ Prints into the console the start of a profile download attachments test with different FDP
        organization.

        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(
            _('\nStarting {v} profile download attachments sub-test for {u} with different FDP organization'.format(
                u=user_role[self._label],
                v=view_txt
            ))
        )

    def __print_profile_download_attachments_without_org(self, user_role, view_txt):
        """ Prints into the console the start of a profile download attachments test without FDP organization.

        :param user_role: Specific user role from self._user_roles for which test is performed.
        :param view_txt: Text defining the specific profile, e.g. officer or command.
        :return: Nothing.
        """
        print(
            _('\nStarting {v} profile download attachments sub-test for {u} without FDP organization'.format(
                u=user_role[self._label],
                v=view_txt
            ))
        )

    def __check_if_in_officer_profile_attachment_downloads(self, pk, fdp_user, fdp_org):
        """ Checks whether attachments with different levels of confidentiality appear in officer profile download
        attachments view for a FDP user.

        :param pk: Primary key for person for which to download officer attachments.
        :param fdp_user: FDP user accessing view.
        :param fdp_org: FDP organization that may be added to the data.
        :return: Nothing.
        """
        attachments = Person.get_officer_attachments(pk=pk, user=fdp_user)
        attachment_names_list = [splitext(f.name)[0] for f in attachments]
        # cycle through all permutations of confidentiality for the row for data
        for confidential in self._confidentials:
            should_data_appear = self._can_user_access_data(
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key],
                has_fdp_org=confidential[self._has_fdp_org_key],
                fdp_user=fdp_user,
                fdp_org=fdp_org
            )
            if should_data_appear:
                self.assertIn(confidential[self._name_key], attachment_names_list)
            else:
                self.assertNotIn(confidential[self._name_key], attachment_names_list)
            print(
                _('{t} is successful ({d} {a})'.format(
                    t=confidential[self._label],
                    d=confidential[self._name_key],
                    a=_('does not appear') if not should_data_appear else _('appears')
                ))
            )

    def __check_if_in_command_profile_attachment_downloads(self, pk, fdp_user, fdp_org):
        """ Checks whether attachments with different levels of confidentiality appear in command profile download
        attachments view for a FDP user.

        :param pk: Primary key for person for which to download command attachments.
        :param fdp_user: FDP user accessing view.
        :param fdp_org: FDP organization that may be added to the data.
        :return: Nothing.
        """
        attachments = Grouping.get_command_attachments(pk=pk, user=fdp_user)
        attachment_names_list = [splitext(f.name)[0] for f in attachments]
        # cycle through all permutations of confidentiality for the row for data
        for confidential in self._confidentials:
            should_data_appear = self._can_user_access_data(
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key],
                has_fdp_org=confidential[self._has_fdp_org_key],
                fdp_user=fdp_user,
                fdp_org=fdp_org
            )
            if should_data_appear:
                self.assertIn(confidential[self._name_key], attachment_names_list)
            else:
                self.assertNotIn(confidential[self._name_key], attachment_names_list)
            print(
                _('{t} is successful ({d} {a})'.format(
                    t=confidential[self._label],
                    d=confidential[self._name_key],
                    a=_('does not appear') if not should_data_appear else _('appears')
                ))
            )

    @classmethod
    def setUpTestData(cls):
        """ Create the categories that are necessary for typing the data to be created during tests.

        :return: Nothing.
        """
        if not PersonRelationshipType.objects.all().exists():
            PersonRelationshipType.objects.create(name='PersonRelationshipType1')
        if not ContentIdentifierType.objects.all().exists():
            ContentIdentifierType.objects.create(name='ContentIdentifierType1')

    def setUp(self):
        """ Ensure data required for tests has been created.

        :return: Nothing.
        """
        self.assertTrue(PersonRelationshipType.objects.all().exists())
        self.assertTrue(ContentIdentifierType.objects.all().exists())

    def __add_persons_for_officer_related_data(self, fdp_org):
        """ Add persons with different confidential levels, and their related data, to the test database.

        Will be used for the Officer profile tests.

        :param fdp_org: FDP organization to use for some of the persons.
        :return: Tuple:
                    - Dictionary of person primary keys corresponding to different confidential levels.
                    - Unrestricted person to whom data is linked.
        """
        self.assertEqual(Person.objects.all().count(), 0)
        # create data without restrictions
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        PersonIncident.objects.create(incident=unrestricted_incident, person=unrestricted_person)
        unrestricted_content = Content.objects.create(name='Name1', **self._not_confidential_dict)
        ContentPerson.objects.create(content=unrestricted_content, person=unrestricted_person)
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        person_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            person = Person.objects.create(
                name=name,
                **self._is_law_dict,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = person.pk
            if confidential[self._has_fdp_org_key]:
                person.fdp_organizations.add(fdp_org)
            person_ids[name] = person.pk
            # connect person to data
            PersonIncident.objects.create(incident=unrestricted_incident, person=person)
            ContentPerson.objects.create(content=unrestricted_content, person=person)
            PersonRelationship.objects.create(
                subject_person=person,
                object_person=unrestricted_person,
                type=PersonRelationshipType.objects.all()[0]
            )
        return person_ids, unrestricted_person

    def __add_persons_for_command_related_data(self, fdp_org):
        """ Add persons for a grouping with different confidential levels, and their related data, to the test database.

        Will be used for the Command profile tests.

        :param fdp_org: FDP organization to use for some of the persons.
        :return: Tuple:
                    - Dictionary of person primary keys corresponding to different confidential levels.
                    - Unrestricted grouping to whom data is linked.
        """
        self.assertEqual(Person.objects.all().count(), 0)
        # create data without restrictions
        unrestricted_grouping = Grouping.objects.create(name='Name1')
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        person_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            person = Person.objects.create(
                name=name,
                **self._is_law_dict,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = person.pk
            if confidential[self._has_fdp_org_key]:
                person.fdp_organizations.add(fdp_org)
            person_ids[name] = person.pk
            # connect person to data
            PersonGrouping.objects.create(grouping=unrestricted_grouping, person=person, is_inactive=True)
            PersonGrouping.objects.create(grouping=unrestricted_grouping, person=person, is_inactive=False)
            incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
            GroupingIncident.objects.create(grouping=unrestricted_grouping, incident=incident)
            PersonIncident.objects.create(person=person, incident=incident)
        return person_ids, unrestricted_grouping

    def __add_incidents_for_officer_related_data(self, fdp_org):
        """ Add incidents with different confidential levels, and their related data, to the test database.

        Used for Officer profile tests.

        :param fdp_org: FDP organization to use for some of the incidents.
        :return: Unrestricted person to whom data is linked.
        """
        self.assertEqual(Incident.objects.all().count(), 0)
        # create data without restrictions
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        # create data with restrictions
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            incident = Incident.objects.create(
                description=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = incident.pk
            if confidential[self._has_fdp_org_key]:
                incident.fdp_organizations.add(fdp_org)
            # connect person to data
            PersonIncident.objects.create(incident=incident, person=unrestricted_person)
        return unrestricted_person

    def __add_incidents_for_command_related_data(self, fdp_org):
        """ Add incidents with different confidential levels, and their related data, to the test database.

        Used for Command profile tests.

        :param fdp_org: FDP organization to use for some of the incidents.
        :return: Unrestricted grouping to whom data is linked.
        """
        self.assertEqual(Incident.objects.all().count(), 0)
        # create data without restrictions
        unrestricted_grouping = Grouping.objects.create(name='Name1')
        unrestricted_person = Person.objects.create(name='Name2', **self._is_law_dict, **self._not_confidential_dict)
        PersonGrouping.objects.create(person=unrestricted_person, grouping=unrestricted_grouping)
        # create data with restrictions
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            incident = Incident.objects.create(
                description=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = incident.pk
            if confidential[self._has_fdp_org_key]:
                incident.fdp_organizations.add(fdp_org)
            # connect grouping to data
            GroupingIncident.objects.create(incident=incident, grouping=unrestricted_grouping)
        return unrestricted_grouping

    def __add_attachments_for_officer_related_data(self, fdp_org):
        """ Add attachments with different confidential levels, and their related data, to the test database.

        Will be used in the Officer profile tests.

        :param fdp_org: FDP organization to use for some of the attachments.
        :return: Unrestricted person to whom data is linked.
        """
        self.assertEqual(Attachment.objects.all().count(), 0)
        # create data without restrictions
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        PersonIncident.objects.create(incident=unrestricted_incident, person=unrestricted_person)
        unrestricted_content_with_incident = Content.objects.create(name='Name1', **self._not_confidential_dict)
        unrestricted_content_with_incident.incidents.add(unrestricted_incident)
        unrestricted_content_without_incident = Content.objects.create(name='Name2', **self._not_confidential_dict)
        ContentPerson.objects.create(content=unrestricted_content_with_incident, person=unrestricted_person)
        ContentPerson.objects.create(content=unrestricted_content_without_incident, person=unrestricted_person)
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            d = {
                'for_admin_only': confidential[self._for_admin_only_key],
                'for_host_only': confidential[self._for_host_only_key],
                'name': name
            }
            link_attachment = Attachment.objects.create(link='https://www.google.com/?x={n}'.format(n=name), **d)
            file_attachment = Attachment.objects.create(file='{n}.txt'.format(n=name), **d)
            self._confidentials[i][self._pk_key] = link_attachment.pk
            if confidential[self._has_fdp_org_key]:
                link_attachment.fdp_organizations.add(fdp_org)
                file_attachment.fdp_organizations.add(fdp_org)
            # connect attachment to data
            unrestricted_content_with_incident.attachments.add(link_attachment)
            unrestricted_content_with_incident.attachments.add(file_attachment)
            unrestricted_content_without_incident.attachments.add(link_attachment)
            unrestricted_content_without_incident.attachments.add(file_attachment)
        return unrestricted_person

    def __add_attachments_for_command_related_data(self, fdp_org):
        """ Add attachments with different confidential levels, and their related data, to the test database.

        Will be used in the Command profile tests.

        :param fdp_org: FDP organization to use for some of the attachments.
        :return: Unrestricted grouping to whom data is linked.
        """
        self.assertEqual(Attachment.objects.all().count(), 0)
        # create data without restrictions
        unrestricted_grouping = Grouping.objects.create(name='Name1')
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        PersonGrouping.objects.create(person=unrestricted_person, grouping=unrestricted_grouping)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        GroupingIncident.objects.create(incident=unrestricted_incident, grouping=unrestricted_grouping)
        unrestricted_content_with_incident = Content.objects.create(name='Name1', **self._not_confidential_dict)
        unrestricted_content_with_incident.incidents.add(unrestricted_incident)
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            d = {
                'for_admin_only': confidential[self._for_admin_only_key],
                'for_host_only': confidential[self._for_host_only_key],
                'name': name
            }
            link_attachment = Attachment.objects.create(link='https://www.google.com/?x={n}'.format(n=name), **d)
            file_attachment = Attachment.objects.create(file='{n}.txt'.format(n=name), **d)
            self._confidentials[i][self._pk_key] = link_attachment.pk
            if confidential[self._has_fdp_org_key]:
                link_attachment.fdp_organizations.add(fdp_org)
                file_attachment.fdp_organizations.add(fdp_org)
            # connect attachment to data
            unrestricted_content_with_incident.attachments.add(link_attachment)
            unrestricted_content_with_incident.attachments.add(file_attachment)
        return unrestricted_grouping

    def __add_contents_for_officer_related_data(self, fdp_org):
        """ Add contents with different confidential levels, and their related data, to the test database.

        Will be used for the Officer profile tests.

        :param fdp_org: FDP organization to use for some of the attachments.
        :return: Unrestricted person to whom data is linked.
        """
        self.assertEqual(Content.objects.all().count(), 0)
        content_identifier_type = ContentIdentifierType.objects.all()[0]
        # create data without restrictions
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        PersonIncident.objects.create(incident=unrestricted_incident, person=unrestricted_person)
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            content_with_incident = Content.objects.create(
                name=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            content_without_incident = Content.objects.create(
                name=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = content_with_incident.pk
            if confidential[self._has_fdp_org_key]:
                content_with_incident.fdp_organizations.add(fdp_org)
                content_without_incident.fdp_organizations.add(fdp_org)
            # connect content to data
            content_with_incident.incidents.add(unrestricted_incident)
            ContentPerson.objects.create(content=content_with_incident, person=unrestricted_person)
            ContentPerson.objects.create(content=content_without_incident, person=unrestricted_person)
            ContentCase.objects.create(content=content_with_incident)
            ContentCase.objects.create(content=content_without_incident)
            ContentIdentifier.objects.create(
                content=content_with_incident,
                identifier=name,
                content_identifier_type=content_identifier_type,
                **self._not_confidential_dict
            )
            ContentIdentifier.objects.create(
                content=content_without_incident,
                identifier=name,
                content_identifier_type=content_identifier_type,
                **self._not_confidential_dict
            )
        return unrestricted_person

    def __add_contents_for_command_related_data(self, fdp_org):
        """ Add contents with different confidential levels, and their related data, to the test database.

        Will be used for the Command profile tests.

        :param fdp_org: FDP organization to use for some of the attachments.
        :return: Unrestricted grouping to whom data is linked.
        """
        self.assertEqual(Content.objects.all().count(), 0)
        content_identifier_type = ContentIdentifierType.objects.all()[0]
        # create data without restrictions
        unrestricted_grouping = Grouping.objects.create(name='Name1')
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        PersonGrouping.objects.create(person=unrestricted_person, grouping=unrestricted_grouping)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        GroupingIncident.objects.create(incident=unrestricted_incident, grouping=unrestricted_grouping)
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            content_with_incident = Content.objects.create(
                name=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = content_with_incident.pk
            if confidential[self._has_fdp_org_key]:
                content_with_incident.fdp_organizations.add(fdp_org)
            # connect content to data
            content_with_incident.incidents.add(unrestricted_incident)
            ContentCase.objects.create(content=content_with_incident)
            ContentIdentifier.objects.create(
                identifier=name,
                content=content_with_incident,
                content_identifier_type=content_identifier_type,
                **self._not_confidential_dict
            )
        return unrestricted_grouping

    def __add_content_identifiers_for_officer_related_data(self, fdp_org):
        """ Add content identifiers with different confidential levels, and their related data, to the test database.

        Will be used for Officer profile tests.

        :param fdp_org: FDP organization to use for some of the content identifiers.
        :return: Unrestricted person to whom data is linked.
        """
        self.assertEqual(ContentIdentifier.objects.all().count(), 0)
        content_identifier_type = ContentIdentifierType.objects.all()[0]
        # create data without restrictions
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        PersonIncident.objects.create(incident=unrestricted_incident, person=unrestricted_person)
        unrestricted_content_with_incident = Content.objects.create(name='Name1', **self._not_confidential_dict)
        unrestricted_content_with_incident.incidents.add(unrestricted_incident)
        unrestricted_content_without_incident = Content.objects.create(name='Name2', **self._not_confidential_dict)
        ContentPerson.objects.create(content=unrestricted_content_with_incident, person=unrestricted_person)
        ContentPerson.objects.create(content=unrestricted_content_without_incident, person=unrestricted_person)
        ContentCase.objects.create(content=unrestricted_content_without_incident)
        ContentCase.objects.create(content=unrestricted_content_with_incident)
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            d = {
                'identifier': name,
                'content_identifier_type': content_identifier_type,
                'for_admin_only': confidential[self._for_admin_only_key],
                'for_host_only': confidential[self._for_host_only_key]
            }
            # connect content identifier to data
            content_identifier_1 = ContentIdentifier.objects.create(content=unrestricted_content_without_incident, **d)
            self._confidentials[i][self._pk_key] = content_identifier_1.pk
            content_identifier_2 = ContentIdentifier.objects.create(content=unrestricted_content_with_incident, **d)
            if confidential[self._has_fdp_org_key]:
                content_identifier_1.fdp_organizations.add(fdp_org)
                content_identifier_2.fdp_organizations.add(fdp_org)
        return unrestricted_person

    def __add_content_identifiers_for_command_related_data(self, fdp_org):
        """ Add content identifiers with different confidential levels, and their related data, to the test database.

        Will be used for Command profile tests.

        :param fdp_org: FDP organization to use for some of the content identifiers.
        :return: Unrestricted grouping to whom data is linked.
        """
        self.assertEqual(ContentIdentifier.objects.all().count(), 0)
        content_identifier_type = ContentIdentifierType.objects.all()[0]
        # create data without restrictions
        unrestricted_grouping = Grouping.objects.create(name='Name1')
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        PersonGrouping.objects.create(person=unrestricted_person, grouping=unrestricted_grouping)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        GroupingIncident.objects.create(incident=unrestricted_incident, grouping=unrestricted_grouping)
        unrestricted_content_with_incident = Content.objects.create(name='Name1', **self._not_confidential_dict)
        unrestricted_content_with_incident.incidents.add(unrestricted_incident)
        ContentCase.objects.create(content=unrestricted_content_with_incident)
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            d = {
                'identifier': name,
                'content_identifier_type': content_identifier_type,
                'for_admin_only': confidential[self._for_admin_only_key],
                'for_host_only': confidential[self._for_host_only_key]
            }
            # connect content identifier to data
            content_identifier = ContentIdentifier.objects.create(content=unrestricted_content_with_incident, **d)
            if confidential[self._has_fdp_org_key]:
                content_identifier.fdp_organizations.add(fdp_org)
        return unrestricted_grouping

    def __delete_persons_for_officer_related_data(self):
        """ Removes all persons and related data from the test database.

        Used for Officer profile tests.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        Incident.objects.all().delete()
        PersonRelationship.objects.all().delete()
        ContentPerson.objects.all().delete()
        Content.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Person.objects.all().count(), 0)

    def __delete_persons_for_command_related_data(self):
        """ Removes all persons and related data from the test database.

        Used for Command profile tests.

        :return: Nothing.
        """
        PersonGrouping.objects.all().delete()
        GroupingIncident.objects.all().delete()
        PersonIncident.objects.all().delete()
        Incident.objects.all().delete()
        Grouping.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Person.objects.all().count(), 0)

    def __delete_incidents_for_officer_related_data(self):
        """ Removes all incidents and related data from the test database.

        Used for Officer profile tests.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        Person.objects.all().delete()
        Incident.objects.all().delete()
        self.assertEqual(Incident.objects.all().count(), 0)

    def __delete_incidents_for_command_related_data(self):
        """ Removes all incidents and related data from the test database.

        Used for Command profile tests.

        :return: Nothing.
        """
        PersonGrouping.objects.all().delete()
        GroupingIncident.objects.all().delete()
        Grouping.objects.all().delete()
        Person.objects.all().delete()
        Incident.objects.all().delete()
        self.assertEqual(Incident.objects.all().count(), 0)

    def __delete_attachments_for_officer_related_data(self):
        """ Removes all attachments and related data from the test database.

        Will be used for Officer profile tests.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        Incident.objects.all().delete()
        PersonRelationship.objects.all().delete()
        ContentPerson.objects.all().delete()
        Content.objects.all().delete()
        Person.objects.all().delete()
        Attachment.objects.all().delete()
        self.assertEqual(Attachment.objects.all().count(), 0)

    def __delete_attachments_for_command_related_data(self):
        """ Removes all attachments and related data from the test database.

        Will be used for Command profile tests.

        :return: Nothing.
        """
        PersonGrouping.objects.all().delete()
        GroupingIncident.objects.all().delete()
        Incident.objects.all().delete()
        Content.objects.all().delete()
        Person.objects.all().delete()
        Grouping.objects.all().delete()
        Attachment.objects.all().delete()
        self.assertEqual(Attachment.objects.all().count(), 0)

    def __delete_contents_for_officer_related_data(self):
        """ Removes all content and related data from the test database.

        Will be used for Officer profile tests.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        Incident.objects.all().delete()
        ContentPerson.objects.all().delete()
        ContentIdentifier.objects.all().delete()
        ContentCase.objects.all().delete()
        Content.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Content.objects.all().count(), 0)

    def __delete_contents_for_command_related_data(self):
        """ Removes all content and related data from the test database.

        Will be used for Command profile tests.

        :return: Nothing.
        """
        PersonGrouping.objects.all().delete()
        GroupingIncident.objects.all().delete()
        Incident.objects.all().delete()
        ContentIdentifier.objects.all().delete()
        ContentCase.objects.all().delete()
        Content.objects.all().delete()
        Grouping.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Content.objects.all().count(), 0)

    def __delete_content_identifiers_for_officer_related_data(self):
        """ Removes all content identifiers and related data from the test database.

        Will be used for Officer profile tests.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        Incident.objects.all().delete()
        PersonRelationship.objects.all().delete()
        ContentPerson.objects.all().delete()
        ContentIdentifier.objects.all().delete()
        ContentCase.objects.all().delete()
        Content.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(ContentIdentifier.objects.all().count(), 0)

    def __delete_content_identifiers_for_command_related_data(self):
        """ Removes all content identifiers and related data from the test database.

        Will be used for Command profile tests.

        :return: Nothing.
        """
        PersonGrouping.objects.all().delete()
        GroupingIncident.objects.all().delete()
        Incident.objects.all().delete()
        ContentIdentifier.objects.all().delete()
        ContentCase.objects.all().delete()
        Content.objects.all().delete()
        Person.objects.all().delete()
        Grouping.objects.all().delete()
        self.assertEqual(ContentIdentifier.objects.all().count(), 0)

    def __test_person_for_officer_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Officer Profile Search Results and Profile Views for all permutations of user roles,
        confidentiality levels and models linked to Person directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add persons with different confidentiality levels
        restricted_persons_dict, unrestricted_person = self.__add_persons_for_officer_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            search_dict = {'admin_only': False, 'search_params': {}}
            load_dict = {'admin_only': False, 'load_params': {}, 'exception_msg': None}
            print_dict = {'model_txt': 'person', 'view_txt': 'officer'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            self._print_profile_load_start_without_org(user_role=user_role, **print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_persons_dict,
                view_name=self._officer_profile_view_name,
                **check_dict,
                **load_dict
            )
            self._print_profile_search_results_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_search_view(**self._officer_profile_search_url_dict, **check_dict, **search_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(url=reverse('profiles:officer', kwargs={'pk': unrestricted_person.pk}), **check_dict)
            self._print_profile_load_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_persons_dict,
                view_name=self._officer_profile_view_name,
                **check_dict,
                **load_dict
            )
            self._print_profile_search_results_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_search_view(**self._officer_profile_search_url_dict, **check_dict, **search_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(url=reverse('profiles:officer', kwargs={'pk': unrestricted_person.pk}), **check_dict)
            self._print_profile_load_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_persons_dict,
                view_name=self._officer_profile_view_name,
                **check_dict,
                **load_dict
            )
            self._print_profile_search_results_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_search_view(**self._officer_profile_search_url_dict, **check_dict, **search_dict)
        # remove persons with different confidentiality levels
        self.__delete_persons_for_officer_related_data()

    def __test_person_for_command_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Command Profile Search Results and Profile Views for all permutations of user roles,
        confidentiality levels and models linked to Person directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add persons with different confidentiality levels
        restricted_persons_dict, unrestricted_grouping = self.__add_persons_for_command_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'person', 'view_txt': 'command'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse('profiles:command', kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse('profiles:command', kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
        # remove persons with different confidentiality levels
        self.__delete_persons_for_command_related_data()

    def __test_incident_for_officer_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Officer Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Incident directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add incidents with different confidentiality levels
        unrestricted_person = self.__add_incidents_for_officer_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'incident', 'view_txt': 'officer'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
        # remove incidents with different confidentiality levels
        self.__delete_incidents_for_officer_related_data()

    def __test_incident_for_command_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Command Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Incident directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add incidents with different confidentiality levels
        unrestricted_grouping = self.__add_incidents_for_command_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'incident', 'view_txt': 'command'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
        # remove incidents with different confidentiality levels
        self.__delete_incidents_for_command_related_data()

    def __test_attachment_for_officer_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Officer Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Attachment directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add attachments with different confidentiality levels
        unrestricted_person = self.__add_attachments_for_officer_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'attachment', 'view_txt': 'officer'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            self.__print_profile_download_attachments_without_org(user_role=user_role, view_txt='officer')
            self.__check_if_in_officer_profile_attachment_downloads(pk=unrestricted_person.pk, **check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            self.__print_profile_download_attachments_with_right_org(user_role=user_role, view_txt='officer')
            self.__check_if_in_officer_profile_attachment_downloads(pk=unrestricted_person.pk, **check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            self.__print_profile_download_attachments_with_wrong_org(user_role=user_role, view_txt='officer')
            self.__check_if_in_officer_profile_attachment_downloads(pk=unrestricted_person.pk, **check_dict)
        # remove attachments with different confidentiality levels
        self.__delete_attachments_for_officer_related_data()

    def __test_attachment_for_command_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Command Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Attachment directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add attachments with different confidentiality levels
        unrestricted_grouping = self.__add_attachments_for_command_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'attachment', 'view_txt': 'command'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            self.__print_profile_download_attachments_without_org(user_role=user_role, view_txt='command')
            self.__check_if_in_command_profile_attachment_downloads(pk=unrestricted_grouping.pk, **check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            self.__print_profile_download_attachments_with_right_org(user_role=user_role, view_txt='command')
            self.__check_if_in_command_profile_attachment_downloads(pk=unrestricted_grouping.pk, **check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            self.__print_profile_download_attachments_with_wrong_org(user_role=user_role, view_txt='command')
            self.__check_if_in_command_profile_attachment_downloads(pk=unrestricted_grouping.pk, **check_dict)
        # remove attachments with different confidentiality levels
        self.__delete_attachments_for_command_related_data()

    def __test_content_for_officer_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Officer Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Content directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add contents with different confidentiality levels
        unrestricted_person = self.__add_contents_for_officer_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'content', 'view_txt': 'officer'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
        # remove contents with different confidentiality levels
        self.__delete_contents_for_officer_related_data()

    def __test_content_for_command_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Command Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Content directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add contents with different confidentiality levels
        unrestricted_grouping = self.__add_contents_for_command_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'content', 'view_txt': 'command'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
        # remove contents with different confidentiality levels
        self.__delete_contents_for_command_related_data()

    def __test_content_identifier_for_officer_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Officer Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Content Identifier directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add content identifiers with different confidentiality levels
        unrestricted_person = self.__add_content_identifiers_for_officer_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'content identifier', 'view_txt': 'officer'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._officer_profile_view_name, kwargs={'pk': unrestricted_person.pk}), **check_dict
            )
        # remove content identifiers with different confidentiality levels
        self.__delete_content_identifiers_for_officer_related_data()

    def __test_content_identifier_for_command_profile_views(self, fdp_org, other_fdp_org):
        """ Test for Command Profile Views for all permutations of user roles, confidentiality levels and models
        linked to Content Identifier directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add content identifiers with different confidentiality levels
        unrestricted_grouping = self.__add_content_identifiers_for_command_related_data(fdp_org=fdp_org)
        # number of users already in database
        num_of_users = FdpUser.objects.all().count() + 1
        # test for all user types
        for i, user_role in enumerate(self._user_roles):
            # skip for anonymous user
            if user_role[self._is_anonymous_key]:
                continue
            # create the FDP user in the test database
            fdp_user = self._create_fdp_user(
                is_host=user_role[self._is_host_key],
                is_administrator=user_role[self._is_administrator_key],
                is_superuser=user_role[self._is_superuser_key],
                email_counter=i + num_of_users
            )
            # keyword arguments to expand as parameters into the check/load methods below
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org}
            print_dict = {'model_txt': 'content identifier', 'view_txt': 'command'}
            # check data for FDP user without FDP org
            self._print_profile_view_start_without_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_right_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_profile_view_start_with_wrong_org(user_role=user_role, **print_dict)
            self._check_if_in_view(
                url=reverse(self._command_profile_view_name, kwargs={'pk': unrestricted_grouping.pk}), **check_dict
            )
        # remove content identifiers with different confidentiality levels
        self.__delete_content_identifiers_for_command_related_data()

    def test_officer_profile_views(self):
        """ Test for Officer profile search results and profile views for all permutations of user roles,
        confidentiality levels and relevant models.

        :return: Nothing
        """
        print(
            _('\nStarting test for Officer Profile Search Results view and Officer Profile view for all permutations '
              'of user roles, confidentiality levels and relevant models')
        )
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization1Profiles')
        other_fdp_org = FdpOrganization.objects.create(name='FdpOrganization2Profiles')
        self.__test_person_for_officer_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_incident_for_officer_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_attachment_for_officer_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_content_for_officer_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_content_identifier_for_officer_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        print(_('\nSuccessfully finished test for for Officer Profile Search Results view and Officer Profile view for '
                'all permutations of user roles, confidentiality levels and relevant models\n\n'))

    def test_command_profile_views(self):
        """ Test for Command profile search results and profile views for all permutations of user roles,
        confidentiality levels and relevant models.

        :return: Nothing
        """
        print(
            _('\nStarting test for Command Profile view for all permutations '
              'of user roles, confidentiality levels and relevant models')
        )
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization3Profiles')
        other_fdp_org = FdpOrganization.objects.create(name='FdpOrganization4Profiles')
        self.__test_person_for_command_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_incident_for_command_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_attachment_for_command_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_content_for_command_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_content_identifier_for_command_profile_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        print(_('\nSuccessfully finished test for for Command Profile view for '
                'all permutations of user roles, confidentiality levels and relevant models\n\n'))
