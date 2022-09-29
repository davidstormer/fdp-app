from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from functional_tests.common import FunctionalTestCase
from inheritable.tests import AbstractTestCase, local_test_settings_required
from fdpuser.models import FdpOrganization, FdpUser
from core.models import Person, PersonRelationship, Incident, PersonIncident
from inheritable.views import SecuredAsyncJsonView
from sourcing.models import Content, ContentPerson, Attachment, ContentIdentifier
from supporting.models import PersonRelationshipType, ContentIdentifierType, Allegation
from .forms import WizardSearchForm
import logging
from django.test import tag

logger = logging.getLogger(__name__)


class ChangingTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test for synchronous Changing Search Results views, Changing Update views, and Link Allegations/Penalties view
    for all permutations of user roles, confidentiality levels and relevant models:
            (A) Person-related views with persons with different levels of confidentiality
            (B) Incident-related views with incidents, persons and content with different levels of confidentiality
            (C) Content-related views with content, persons, incidents, attachments and content identifiers with
                different levels of confidentiality
            (D) Link Allegations/Penalties view with content, persons, incidents, attachments and content identifiers
                with different levels of confidentiality

    (2) Test for Changing asynchronous views for all permutations of user roles, confidentiality levels and relevant
    models:
            (A) Persons with different levels of confidentiality
            (B) Attachments with different levels of confidentiality
            (C) Incidents with different levels of confidentiality

    """
    #: Dictionary that can be expanded into keyword arguments to define changing person searching URLs.
    _changing_person_search_url_dict = {
        'search_url': reverse('changing:persons'),
        'search_results_url': reverse('changing:list', kwargs={'type': WizardSearchForm.person_type})
    }

    #: Dictionary that can be expanded into keyword arguments to define changing incident searching URLs.
    _changing_incident_search_url_dict = {
        'search_url': reverse('changing:incidents'),
        'search_results_url': reverse('changing:list', kwargs={'type': WizardSearchForm.incident_type})
    }

    #: Dictionary that can be expanded into keyword arguments to define changing content searching URLs.
    _changing_content_search_url_dict = {
        'search_url': reverse('changing:content'),
        'search_results_url': reverse('changing:list', kwargs={'type': WizardSearchForm.content_type})
    }

    #: View name parameter for reverse(...) when generating changing person update URL.
    _changing_update_person_view_name = 'changing:edit_person'

    #: View name parameter for reverse(...) when generating changing incident update URL.
    _changing_update_incident_view_name = 'changing:edit_incident'

    #: View name parameter for reverse(...) when generating changing content update URL.
    _changing_update_content_view_name = 'changing:edit_content'

    #: View name parameter for reverse(...) when generating changing linking allegations/penalties URL.
    _changing_link_allegations_penalties_view_name = 'changing:link_allegations_penalties'

    @classmethod
    def setUpTestData(cls):
        """ Create the categories that are necessary for typing the data to be created during tests.

        :return: Nothing.
        """
        if not PersonRelationshipType.objects.all().exists():
            PersonRelationshipType.objects.create(name='PersonRelationshipType1')
        if not ContentIdentifierType.objects.all().exists():
            ContentIdentifierType.objects.create(name='ContentIdentifierType1')
        if not Allegation.objects.all().exists():
            Allegation.objects.create(name='Name1')

    def setUp(self):
        """ Ensure data required for tests has been created.

        :return: Nothing.
        """
        # skip setup and tests unless configuration is compatible
        super().setUp()
        self.assertTrue(PersonRelationshipType.objects.all().exists())
        self.assertTrue(ContentIdentifierType.objects.all().exists())
        self.assertTrue(Allegation.objects.all().exists())

    def __add_attachment_views_related_data(self, fdp_org):
        """ Add attachment with different confidential levels, and their related and relevant data, to the test
        database.

        Used for attachment-related views in the data wizard.

        :param fdp_org: FDP organization to use for some of the attachment.
        :return: Dictionary of attachment primary keys corresponding to different confidentiality levels.
        """
        self.assertEqual(Attachment.objects.all().count(), 0)
        attachment_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            attachment = Attachment.objects.create(
                name=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = attachment.pk
            if confidential[self._has_fdp_org_key]:
                attachment.fdp_organizations.add(fdp_org)
            attachment_ids[name] = attachment.pk
        return attachment_ids

    def __add_content_views_related_data(self, fdp_org):
        """ Add content with different confidential levels, and their related and relevant data, to the test database.

        Used for content-related views in the data wizard.

        :param fdp_org: FDP organization to use for some of the content.
        :return: Dictionary of content primary keys corresponding to different confidentiality levels.
        """
        self.assertEqual(Content.objects.all().count(), 0)
        content_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            content = Content.objects.create(
                name=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = content.pk
            if confidential[self._has_fdp_org_key]:
                content.fdp_organizations.add(fdp_org)
            content_ids[name] = content.pk
        return content_ids

    def __add_person_views_related_data(self, fdp_org):
        """ Add persons with different confidential levels, and their related and relevant data, to the test database.

        Used for person-related views in the data wizard.

        :param fdp_org: FDP organization to use for some of the persons.
        :return: Dictionary of person primary keys corresponding to different confidentiality levels.
        """
        self.assertEqual(Person.objects.all().count(), 0)
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
        return person_ids

    def __add_confidential_person_relationships(self, restricted_person_ids):
        """ Add person relationships that include one person with a level of confidentiality.

        :param restricted_person_ids: Dictionary of person primary keys corresponding to different confidential levels.
        :return: Dictionary of primary keys for unrestricted persons linked through person relationships to persons
        with different confidential levels.
        """
        person_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            person_id = restricted_person_ids[name]
            another_person = Person.objects.create(name=name, **self._is_law_dict, **self._not_confidential_dict)
            person_ids[name] = another_person.pk
            # create relationship between another unrestricted person and person with a level of confidentiality
            PersonRelationship.objects.create(
                subject_person=Person.objects.get(pk=person_id),
                object_person=another_person,
                type=PersonRelationshipType.objects.all()[0]
            )
        return person_ids

    def __add_incident_views_related_data(self, fdp_org):
        """ Add incidents with different confidential levels, and their related and relevant data, to the test database.

        Used for incident-related views in the data wizard.

        :param fdp_org: FDP organization to use for some of the incidents.
        :return: Dictionary of incident primary keys corresponding to different confidentiality levels.
        """
        self.assertEqual(Incident.objects.all().count(), 0)
        incident_ids = {}
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
            incident_ids[name] = incident.pk
        return incident_ids

    def __add_confidential_person_incidents(self, fdp_org):
        """ Add person incidents that include a person with a level of confidentiality.

        :param fdp_org: FDP organization to use for some of the people.
        :return: Dictionary of primary keys for unrestricted incidents linked through person incidents to persons
        with different confidentiality levels.
        """
        # add persons with different confidentiality levels
        restricted_person_ids = self.__add_person_views_related_data(fdp_org)
        incident_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            incident = Incident.objects.create(description='', **self._not_confidential_dict)
            person_id = restricted_person_ids[name]
            incident_ids[name] = incident.pk
            # create link between unrestricted incident and person with a level of confidentiality
            PersonIncident.objects.create(person=Person.objects.get(pk=person_id), incident=incident)
        return incident_ids

    def __add_confidential_content_for_incident(self, fdp_org):
        """ Add content with a level of confidentiality that is indirectly linked to an incident.

        :param fdp_org: FDP organization to use for some of the content.
        :return: Unrestricted incident linked indirectly to content with different confidentiality levels.
        """
        incident = Incident.objects.create(description='', **self._not_confidential_dict)
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            person = Person.objects.create(name=name, **self._is_law_dict, **self._not_confidential_dict)
            content = Content.objects.create(
                name='Content{i}'.format(i=i),
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = content.pk
            if confidential[self._has_fdp_org_key]:
                content.fdp_organizations.add(fdp_org)
            content.incidents.add(incident)
            ContentPerson.objects.create(person=person, content=content)
        return incident

    def __add_confidential_person_for_incident(self, fdp_org):
        """ Add person with a level of confidentiality that is indirectly linked to an incident.

        :param fdp_org: FDP organization to use for some of the people.
        :return: Unrestricted incident linked indirectly to people with different confidentiality levels.
        """
        incident = Incident.objects.create(description='', **self._not_confidential_dict)
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            content = Content.objects.create(name='Content{i}'.format(i=i), **self._not_confidential_dict)
            person = Person.objects.create(
                name=name,
                **self._is_law_dict,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = person.pk
            if confidential[self._has_fdp_org_key]:
                person.fdp_organizations.add(fdp_org)
            content.incidents.add(incident)
            ContentPerson.objects.create(person=person, content=content)
        return incident

    def __add_confidential_incidents_for_content(self, fdp_org):
        """ Add incidents with a level of confidentiality linked to unrestricted content.

        :param fdp_org: FDP organization to use for some of the incidents.
        :return: Dictionary of primary keys for unrestricted content linked to incidents with different
        confidentiality levels.
        """
        # add incidents with different confidentiality levels
        restricted_incident_ids = self.__add_incident_views_related_data(fdp_org)
        content_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            content = Content.objects.create(name='', **self._not_confidential_dict)
            incident_id = restricted_incident_ids[name]
            content_ids[name] = content.pk
            # create link between unrestricted content and incident with a level of confidentiality
            content.incidents.add(Incident.objects.get(pk=incident_id))
        return content_ids

    def __add_confidential_attachments_for_content(self, fdp_org):
        """ Add attachments with a level of confidentiality linked to unrestricted content.

        :param fdp_org: FDP organization to use for some of the attachments.
        :return: Dictionary of primary keys for unrestricted content linked to attachments with different
        confidentiality levels.
        """
        content_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            attachment = Attachment.objects.create(
                name=name,
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = attachment.pk
            if confidential[self._has_fdp_org_key]:
                attachment.fdp_organizations.add(fdp_org)
            content = Content.objects.create(name='', **self._not_confidential_dict)
            content_ids[name] = content.pk
            # create link between unrestricted content and attachment with a level of confidentiality
            content.attachments.add(attachment)
        return content_ids

    def __add_confidential_persons_for_content(self, fdp_org):
        """ Add persons with a level of confidentiality linked to unrestricted content.

        :param fdp_org: FDP organization to use for some of the persons.
        :return: Dictionary of primary keys for unrestricted content linked to persons with different
        confidentiality levels.
        """
        # add people with different confidentiality levels
        restricted_person_ids = self.__add_person_views_related_data(fdp_org)
        content_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            person_id = restricted_person_ids[name]
            content = Content.objects.create(name='', **self._not_confidential_dict)
            content_ids[name] = content.pk
            # create link between unrestricted content and person with a level of confidentiality
            ContentPerson.objects.create(content=content, person=Person.objects.get(pk=person_id))
        return content_ids

    def __add_confidential_identifiers_for_content(self, fdp_org):
        """ Add identifiers with a level of confidentiality linked to unrestricted content.

        :param fdp_org: FDP organization to use for some of the identifiers.
        :return: Dictionary of primary keys for unrestricted content linked to identifiers with different
        confidentiality levels.
        """
        content_ids = {}
        for i, confidential in enumerate(self._confidentials):
            name = confidential[self._name_key]
            content = Content.objects.create(name='', **self._not_confidential_dict)
            content_ids[name] = content.pk
            # create link between unrestricted content and identifier with a level of confidentiality
            content_identifier = ContentIdentifier.objects.create(
                content=content,
                identifier=name,
                content_identifier_type=ContentIdentifierType.objects.all()[0],
                for_admin_only=confidential[self._for_admin_only_key],
                for_host_only=confidential[self._for_host_only_key]
            )
            self._confidentials[i][self._pk_key] = content_identifier.pk
            if confidential[self._has_fdp_org_key]:
                content_identifier.fdp_organizations.add(fdp_org)
        return content_ids

    def __delete_confidential_identifiers_for_content(self, content_ids_to_delete):
        """ Removes all content identifiers from the test database.

        :param content_ids_to_delete: List of primary keys referencing content to delete.
        :return: Nothing.
        """
        ContentIdentifier.objects.all().delete()
        Content.objects.filter(pk__in=content_ids_to_delete).delete()
        self.assertEqual(ContentIdentifier.objects.all().count(), 0)

    def __delete_confidential_persons_for_content(self, content_ids_to_delete):
        """ Removes all persons from the test database.

        :param content_ids_to_delete: List of primary keys referencing content to delete.
        :return: Nothing.
        """
        ContentPerson.objects.all().delete()
        self.__delete_person_views_related_data()
        Content.objects.filter(pk__in=content_ids_to_delete).delete()
        self.assertEqual(Person.objects.all().count(), 0)

    def __delete_confidential_incidents_for_content(self, content_ids_to_delete):
        """ Removes all incidents from the test database.

        :param content_ids_to_delete: List of primary keys referencing content to delete.
        :return: Nothing.
        """
        self.__delete_incident_views_related_data()
        Content.objects.filter(pk__in=content_ids_to_delete).delete()
        self.assertEqual(Incident.objects.all().count(), 0)

    def __delete_confidential_attachments_for_content(self, content_ids_to_delete):
        """ Removes all attachments from the test database.

        :param content_ids_to_delete: List of primary keys referencing content to delete.
        :return: Nothing.
        """
        Attachment.objects.all().delete()
        Content.objects.filter(pk__in=content_ids_to_delete).delete()
        self.assertEqual(Attachment.objects.all().count(), 0)

    def __delete_confidential_person_relationships(self, person_ids_to_delete):
        """ Removes all person relationships from the test database.

        :param person_ids_to_delete: List of primary keys referencing people to delete.
        :return: Nothing.
        """
        PersonRelationship.objects.all().delete()
        Person.objects.filter(pk__in=person_ids_to_delete).delete()
        self.assertEqual(PersonRelationship.objects.all().count(), 0)

    def __delete_confidential_person_incidents(self, incident_ids_to_delete):
        """ Removes all person incidents from the test database.

        :param incident_ids_to_delete: List of primary keys referencing incidents to delete.
        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        self.__delete_person_views_related_data()
        Incident.objects.filter(pk__in=incident_ids_to_delete).delete()
        self.assertEqual(PersonIncident.objects.all().count(), 0)

    def __delete_confidential_content_for_incidents(self, incident_ids_to_delete):
        """ Removes all content indirectly linked to incidents from the test database.

        :param incident_ids_to_delete: List of primary keys referencing incidents to delete.
        :return: Nothing.
        """
        ContentPerson.objects.all().delete()
        Person.objects.all().delete()
        Incident.objects.filter(pk__in=incident_ids_to_delete).delete()
        Content.objects.all().delete()
        self.assertEqual(Content.objects.all().count(), 0)

    def __delete_confidential_person_for_incidents(self, incident_ids_to_delete):
        """ Removes all people indirectly linked to incidents from the test database.

        :param incident_ids_to_delete: List of primary keys referencing incidents to delete.
        :return: Nothing.
        """
        ContentPerson.objects.all().delete()
        Person.objects.all().delete()
        Incident.objects.filter(pk__in=incident_ids_to_delete).delete()
        Content.objects.all().delete()
        self.assertEqual(Person.objects.all().count(), 0)

    def __delete_attachment_views_related_data(self):
        """ Removes all attachment and their related and relevant data from the test database.

        :return: Nothing.
        """
        Attachment.objects.all().delete()
        self.assertEqual(Attachment.objects.all().count(), 0)

    def __delete_content_views_related_data(self):
        """ Removes all content and their related and relevant data from the test database.

        :return: Nothing.
        """
        Content.objects.all().delete()
        self.assertEqual(Content.objects.all().count(), 0)

    def __delete_person_views_related_data(self):
        """ Removes all persons and their related and relevant data from the test database.

        :return: Nothing.
        """
        PersonRelationship.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Person.objects.all().count(), 0)

    def __delete_incident_views_related_data(self):
        """ Removes all incidents and their related and relevant data from the test database.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        Person.objects.all().delete()
        Incident.objects.all().delete()
        self.assertEqual(Incident.objects.all().count(), 0)

    def __check_if_content_appears_in_incident_update_view(self, fdp_user, fdp_org, user_role):
        """ Check if persons linked to incident through content with different confidentiality levels appears in an
        incident update view in the data wizard.

        :param fdp_user: User accessing view.
        :param fdp_org: FDP organization that may be linked to the data.
        :param user_role: User role through which FDP user was created.
        :return: Nothing
        """
        # only test for administrators and super users
        if not (fdp_user.is_administrator or fdp_user.is_superuser):
            return
        self._print_changing_update_start_without_org(
            view_txt='incident',
            model_txt='content indirectly linked to incident',
            user_role=user_role
        )
        unrestricted_incident = self.__add_confidential_content_for_incident(fdp_org=fdp_org)
        self._check_if_in_view(
            url=reverse(
                self._changing_update_incident_view_name,
                kwargs={'pk': unrestricted_incident.pk, 'content_id': 0}
            ),
            fdp_user=fdp_user,
            fdp_org=fdp_org
        )
        self.__delete_confidential_content_for_incidents(incident_ids_to_delete=[unrestricted_incident.pk])

    def __check_if_person_appears_in_incident_update_view(self, fdp_user, fdp_org, user_role):
        """ Check if persons with different confidentiality levels that are linked to an incident through content
        appear in an incident update view in the data wizard.

        :param fdp_user: User accessing view.
        :param fdp_org: FDP organization that may be linked to the data.
        :param user_role: User role through which FDP user was created.
        :return: Nothing
        """
        # only test for administrators and super users
        if not (fdp_user.is_administrator or fdp_user.is_superuser):
            return
        self._print_changing_update_start_without_org(
            view_txt='incident',
            model_txt='person indirectly linked to incident',
            user_role=user_role
        )
        unrestricted_incident = self.__add_confidential_person_for_incident(fdp_org=fdp_org)
        self._check_if_in_view(
            url=reverse(
                self._changing_update_incident_view_name,
                kwargs={'pk': unrestricted_incident.pk, 'content_id': 0}
            ),
            fdp_user=fdp_user,
            fdp_org=fdp_org
        )
        self.__delete_confidential_person_for_incidents(incident_ids_to_delete=[unrestricted_incident.pk])

    def __test_person_changing_sync_views(self, fdp_org, other_fdp_org):
        """ Test for Changing Person Search Results view, Changing Person Update view for all
        permutations of user roles, confidentiality levels and models linked to Person directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add persons with different confidentiality levels
        restricted_persons_dict = self.__add_person_views_related_data(fdp_org=fdp_org)
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
            print_dict = {'view_txt': 'person', 'model_txt': 'person', 'user_role': user_role}
            print_rel_dict = {'view_txt': 'person', 'model_txt': 'person relationship', 'user_role': user_role}
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org, 'admin_only': True}
            relationship_dict = {'restricted_person_ids': restricted_persons_dict}
            search_dict = {'search_params': {'type': WizardSearchForm.person_type}}
            load_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to update this object'}
            load_rel_dict = {
                'load_params': {},
                'exception_msg': 'User does not have permission to a person-relationship'
            }
            # check data for FDP user without FDP org
            self._print_changing_search_results_start_without_org(**print_dict)
            self._check_if_in_search_view(**self._changing_person_search_url_dict, **check_dict, **search_dict)
            unrestricted_persons_dict = self.__add_confidential_person_relationships(**relationship_dict)
            self._print_changing_update_start_without_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_persons_dict,
                view_name=self._changing_update_person_view_name,
                **check_dict,
                **load_dict
            )
            self._print_changing_update_start_without_org(**print_rel_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_persons_dict,
                view_name=self._changing_update_person_view_name,
                **check_dict,
                **load_rel_dict
            )
            self.__delete_confidential_person_relationships(person_ids_to_delete=unrestricted_persons_dict.values())
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_search_results_start_with_right_org(**print_dict)
            self._check_if_in_search_view(**self._changing_person_search_url_dict, **check_dict, **search_dict)
            unrestricted_persons_dict = self.__add_confidential_person_relationships(**relationship_dict)
            self._print_changing_update_start_with_right_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_persons_dict,
                view_name=self._changing_update_person_view_name,
                **check_dict,
                **load_dict
            )
            self._print_changing_update_start_with_right_org(**print_rel_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_persons_dict,
                view_name=self._changing_update_person_view_name,
                **check_dict,
                **load_rel_dict
            )
            self.__delete_confidential_person_relationships(person_ids_to_delete=unrestricted_persons_dict.values())
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_search_results_start_with_wrong_org(**print_dict)
            self._check_if_in_search_view(**self._changing_person_search_url_dict, **check_dict, **search_dict)
            unrestricted_persons_dict = self.__add_confidential_person_relationships(**relationship_dict)
            self._print_changing_update_start_with_wrong_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_persons_dict,
                view_name=self._changing_update_person_view_name,
                **check_dict,
                **load_dict
            )
            self._print_changing_update_start_with_wrong_org(**print_rel_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_persons_dict,
                view_name=self._changing_update_person_view_name,
                **check_dict,
                **load_rel_dict
            )
            self.__delete_confidential_person_relationships(person_ids_to_delete=unrestricted_persons_dict.values())
        # remove persons with different confidentiality levels
        self.__delete_person_views_related_data()

    def __test_incident_changing_sync_views(self, fdp_org, other_fdp_org):
        """ Test for Changing Incident Search Results view, Changing Incident Update view for all
        permutations of user roles, confidentiality levels and models linked to Incident directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add incidents with different confidentiality levels
        restricted_incidents_dict = self.__add_incident_views_related_data(fdp_org=fdp_org)
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
            print_dict = {'view_txt': 'incident', 'model_txt': 'incident', 'user_role': user_role}
            print_pi_dict = {'view_txt': 'incident', 'model_txt': 'person incident', 'user_role': user_role}
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org, 'admin_only': True}
            link_dict = {'fdp_org': fdp_org}
            search_dict = {'search_params': {'type': WizardSearchForm.incident_type}}
            load_dict = {
                'load_params': {'content_id': 0},
                'exception_msg': 'User does not have permission to update this object'
            }
            load_pi_dict = {
                'load_params': {'content_id': 0},
                'exception_msg': 'User does not have permission to a person-incident'
            }
            check_co_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org, 'user_role': user_role}
            # check data for FDP user without FDP org
            self._print_changing_search_results_start_without_org(**print_dict)
            self._check_if_in_search_view(**self._changing_incident_search_url_dict, **check_dict, **search_dict)
            unrestricted_incidents_dict = self.__add_confidential_person_incidents(**link_dict)
            self._print_changing_update_start_without_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_incidents_dict,
                view_name=self._changing_update_incident_view_name,
                **check_dict,
                **load_dict
            )
            self._print_changing_update_start_without_org(**print_pi_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_incidents_dict,
                view_name=self._changing_update_incident_view_name,
                **check_dict,
                **load_pi_dict
            )
            self.__delete_confidential_person_incidents(incident_ids_to_delete=unrestricted_incidents_dict.values())
            self.__check_if_content_appears_in_incident_update_view(**check_co_dict)
            self.__check_if_person_appears_in_incident_update_view(**check_co_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_search_results_start_with_right_org(**print_dict)
            self._check_if_in_search_view(**self._changing_incident_search_url_dict, **check_dict, **search_dict)
            unrestricted_incidents_dict = self.__add_confidential_person_incidents(**link_dict)
            self._print_changing_update_start_with_right_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_incidents_dict,
                view_name=self._changing_update_incident_view_name,
                **check_dict,
                **load_dict
            )
            self._print_changing_update_start_with_right_org(**print_pi_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_incidents_dict,
                view_name=self._changing_update_incident_view_name,
                **check_dict,
                **load_pi_dict
            )
            self.__delete_confidential_person_incidents(incident_ids_to_delete=unrestricted_incidents_dict.values())
            self.__check_if_content_appears_in_incident_update_view(**check_co_dict)
            self.__check_if_person_appears_in_incident_update_view(**check_co_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_search_results_start_with_wrong_org(**print_dict)
            self._check_if_in_search_view(**self._changing_incident_search_url_dict, **check_dict, **search_dict)
            unrestricted_incidents_dict = self.__add_confidential_person_incidents(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_incidents_dict,
                view_name=self._changing_update_incident_view_name,
                **check_dict,
                **load_dict
            )
            self._print_changing_update_start_with_wrong_org(**print_pi_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_incidents_dict,
                view_name=self._changing_update_incident_view_name,
                **check_dict,
                **load_pi_dict
            )
            self.__delete_confidential_person_incidents(incident_ids_to_delete=unrestricted_incidents_dict.values())
            self.__check_if_content_appears_in_incident_update_view(**check_co_dict)
            self.__check_if_person_appears_in_incident_update_view(**check_co_dict)
        # remove incidents with different confidentiality levels
        self.__delete_incident_views_related_data()

    def __test_content_changing_sync_views(self, fdp_org, other_fdp_org):
        """ Test for Changing Content Search Results view and Changing Content Update view for all permutations of
        user roles, confidentiality levels and models linked to Content directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add content with different confidentiality levels
        restricted_content_dict = self.__add_content_views_related_data(fdp_org=fdp_org)
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
            print_dict = {'view_txt': 'content', 'model_txt': 'content', 'user_role': user_role}
            print_i_dict = {'view_txt': 'content', 'model_txt': 'content incident', 'user_role': user_role}
            print_a_dict = {'view_txt': 'content', 'model_txt': 'content attachment', 'user_role': user_role}
            print_cp_dict = {'view_txt': 'content', 'model_txt': 'content person', 'user_role': user_role}
            print_ci_dict = {'view_txt': 'content', 'model_txt': 'content identifier', 'user_role': user_role}
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org, 'admin_only': True}
            link_dict = {'fdp_org': fdp_org}
            search_dict = {'search_params': {'type': WizardSearchForm.content_type}}
            load_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to update this object'}
            load_i_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to an incident'}
            load_cp_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to a content-person'}
            load_ci_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to a content-identifier'}
            # check data for FDP user without FDP org
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(fdp_org=fdp_org)
            self._print_changing_search_results_start_without_org(**print_dict)
            self._check_if_in_search_view(**self._changing_content_search_url_dict, **check_dict, **search_dict)
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            self._print_changing_update_start_without_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_dict
            )
            # incidents for content
            unrestricted_content_dict = self.__add_confidential_incidents_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_i_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_i_dict
            )
            self.__delete_confidential_incidents_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # attachments for content
            unrestricted_content_dict = self.__add_confidential_attachments_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_a_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_dict
            )
            self.__delete_confidential_attachments_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # persons for content
            unrestricted_content_dict = self.__add_confidential_persons_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_cp_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_cp_dict
            )
            self.__delete_confidential_persons_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # identifiers for content
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_ci_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_ci_dict
            )
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(fdp_org=fdp_org)
            self._print_changing_search_results_start_with_right_org(**print_dict)
            self._check_if_in_search_view(**self._changing_content_search_url_dict, **check_dict, **search_dict)
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            self._print_changing_update_start_with_right_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_dict
            )
            # incidents for content
            unrestricted_content_dict = self.__add_confidential_incidents_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_i_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_i_dict
            )
            self.__delete_confidential_incidents_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # attachments for content
            unrestricted_content_dict = self.__add_confidential_attachments_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_a_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_dict
            )
            self.__delete_confidential_attachments_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # persons for content
            unrestricted_content_dict = self.__add_confidential_persons_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_cp_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_cp_dict
            )
            self.__delete_confidential_persons_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # identifiers for content
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_ci_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_ci_dict
            )
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(fdp_org=fdp_org)
            self._print_changing_search_results_start_with_wrong_org(**print_dict)
            self._check_if_in_search_view(**self._changing_content_search_url_dict, **check_dict, **search_dict)
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            self._print_changing_update_start_with_wrong_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_dict
            )
            # incidents for content
            unrestricted_content_dict = self.__add_confidential_incidents_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_i_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_i_dict
            )
            self.__delete_confidential_incidents_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # attachments for content
            unrestricted_content_dict = self.__add_confidential_attachments_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_a_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_dict
            )
            self.__delete_confidential_attachments_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # persons for content
            unrestricted_content_dict = self.__add_confidential_persons_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_cp_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_cp_dict
            )
            self.__delete_confidential_persons_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # identifiers for content
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_ci_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_update_content_view_name,
                **check_dict,
                **load_ci_dict
            )
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
        # remove content with different confidentiality levels
        self.__delete_content_views_related_data()

    def __test_link_allegations_penalties_changing_sync_views(self, fdp_org, other_fdp_org):
        """ Test for Changing Linking Allegations/Penalties view for all permutations of user roles, confidentiality
        levels and models linked to Content directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add content with different confidentiality levels
        restricted_content_dict = self.__add_content_views_related_data(fdp_org=fdp_org)
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
            print_dict = {'view_txt': 'link allegations/penalties', 'model_txt': 'content', 'user_role': user_role}
            print_i_dict = {
                'view_txt': 'link allegations/penalties', 'model_txt': 'content incident', 'user_role': user_role
            }
            print_a_dict = {
                'view_txt': 'link allegations/penalties', 'model_txt': 'content attachment', 'user_role': user_role
            }
            print_cp_dict = {
                'view_txt': 'link allegations/penalties', 'model_txt': 'content person', 'user_role': user_role
            }
            print_ci_dict = {
                'view_txt': 'link allegations/penalties', 'model_txt': 'content identifier', 'user_role': user_role
            }
            check_dict = {'fdp_user': fdp_user, 'fdp_org': fdp_org, 'admin_only': True}
            link_dict = {'fdp_org': fdp_org}
            load_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to update this object'}
            load_i_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to an incident'}
            load_cp_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to a content-person'}
            load_ci_dict = {'load_params': {}, 'exception_msg': 'User does not have permission to a content-identifier'}
            # check data for FDP user without FDP org
            self._print_changing_update_start_without_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_dict
            )
            # incidents for content
            unrestricted_content_dict = self.__add_confidential_incidents_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_i_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_i_dict
            )
            self.__delete_confidential_incidents_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # attachments for content
            unrestricted_content_dict = self.__add_confidential_attachments_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_a_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_dict
            )
            self.__delete_confidential_attachments_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # persons for content
            unrestricted_content_dict = self.__add_confidential_persons_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_cp_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_cp_dict
            )
            self.__delete_confidential_persons_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # identifiers for content
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(**link_dict)
            self._print_changing_update_start_without_org(**print_ci_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_ci_dict
            )
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_right_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_dict
            )
            # incidents for content
            unrestricted_content_dict = self.__add_confidential_incidents_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_i_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_i_dict
            )
            self.__delete_confidential_incidents_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # attachments for content
            unrestricted_content_dict = self.__add_confidential_attachments_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_a_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_dict
            )
            self.__delete_confidential_attachments_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # persons for content
            unrestricted_content_dict = self.__add_confidential_persons_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_cp_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_cp_dict
            )
            self.__delete_confidential_persons_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # identifiers for content
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(**link_dict)
            self._print_changing_update_start_with_right_org(**print_ci_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_ci_dict
            )
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_wrong_org(**print_dict)
            self._check_if_load_view(
                id_map_dict=restricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_dict
            )
            # incidents for content
            unrestricted_content_dict = self.__add_confidential_incidents_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_i_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_i_dict
            )
            self.__delete_confidential_incidents_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # attachments for content
            unrestricted_content_dict = self.__add_confidential_attachments_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_a_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_dict
            )
            self.__delete_confidential_attachments_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # persons for content
            unrestricted_content_dict = self.__add_confidential_persons_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_cp_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_cp_dict
            )
            self.__delete_confidential_persons_for_content(content_ids_to_delete=unrestricted_content_dict.values())
            # identifiers for content
            unrestricted_content_dict = self.__add_confidential_identifiers_for_content(**link_dict)
            self._print_changing_update_start_with_wrong_org(**print_ci_dict)
            self._check_if_load_view(
                id_map_dict=unrestricted_content_dict,
                view_name=self._changing_link_allegations_penalties_view_name,
                **check_dict,
                **load_ci_dict
            )
            self.__delete_confidential_identifiers_for_content(content_ids_to_delete=unrestricted_content_dict.values())
        # remove content with different confidentiality levels
        self.__delete_content_views_related_data()

    def __test_person_changing_async_view(self, fdp_org, other_fdp_org):
        """ Test for asynchronous Changing Person view for all permutations of user roles, confidentiality levels
        and models linked to Person directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add persons with different confidentiality levels
        self.__add_person_views_related_data(fdp_org=fdp_org)
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
            print_dict = {'view_txt': 'person', 'model_txt': 'person', 'user_role': user_role}
            check_dict = {
                'url': reverse('changing:async_get_persons'),
                'fdp_user': fdp_user,
                'fdp_org': fdp_org,
                'admin_only': True
            }
            # check data for FDP user without FDP org
            self._print_changing_update_start_without_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_right_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_wrong_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
        # remove persons with different confidentiality levels
        self.__delete_person_views_related_data()

    def __test_incident_changing_async_view(self, fdp_org, other_fdp_org):
        """ Test for asynchronous Changing Incident view for all permutations of user roles, confidentiality levels
        and models linked to Incident directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add incidents with different confidentiality levels
        self.__add_incident_views_related_data(fdp_org=fdp_org)
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
            print_dict = {'view_txt': 'incident', 'model_txt': 'incident', 'user_role': user_role}
            check_dict = {
                'url': reverse('changing:async_get_incidents'),
                'fdp_user': fdp_user,
                'fdp_org': fdp_org,
                'admin_only': True
            }
            # check data for FDP user without FDP org
            self._print_changing_update_start_without_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_right_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_wrong_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
        # remove incidents with different confidentiality levels
        self.__delete_incident_views_related_data()

    def __test_attachment_changing_async_view(self, fdp_org, other_fdp_org):
        """ Test for asynchronous Changing Attachment view for all permutations of user roles, confidentiality levels
        and models linked to Attachment directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add attachments with different confidentiality levels
        self.__add_attachment_views_related_data(fdp_org=fdp_org)
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
            print_dict = {'view_txt': 'attachment', 'model_txt': 'attachment', 'user_role': user_role}
            check_dict = {
                'url': reverse('changing:async_get_attachments'),
                'fdp_user': fdp_user,
                'fdp_org': fdp_org,
                'admin_only': True
            }
            # check data for FDP user without FDP org
            self._print_changing_update_start_without_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_right_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changing_update_start_with_wrong_org(**print_dict)
            self._check_if_in_async_changing_view(**check_dict)
        # remove attachments with different confidentiality levels
        self.__delete_attachment_views_related_data()

    def test_changing_sync_views(self):
        """ Test for synchronous Changing Search Results views, Changing Update views, and Link Allegations/Penalties
        view for all permutations of user roles, confidentiality levels and relevant models.

        :return: Nothing
        """
        logger.debug(
            _('\nStarting test for synchronous Changing Search Results views, Changing Update views, and Link '
              'Allegations/Penalties view for all permutations of user roles, confidentiality levels and relevant '
              'models')
        )
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization1Changing')
        other_fdp_org = FdpOrganization.objects.create(name='FdpOrganization2Changing')
        self.__test_person_changing_sync_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_incident_changing_sync_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_content_changing_sync_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_link_allegations_penalties_changing_sync_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        logger.debug(_('\nSuccessfully finished test for synchronous Changing Search Results views, Changing Update views, '
                'and Link Allegations/Penalties view for all permutations of user roles, confidentiality levels and '
                'relevant models\n\n'))

    def test_changing_async_views(self):
        """ Test for Changing asynchronous views for all permutations of user roles, confidentiality levels and
        relevant models.

        :return: Nothing
        """
        logger.debug(
            _('\nStarting test for asynchronous Changing views for all permutations of user roles, confidentiality '
              'levels and relevant models')
        )
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization3Changing')
        other_fdp_org = FdpOrganization.objects.create(name='FdpOrganization4Changing')
        self.__test_person_changing_async_view(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_incident_changing_async_view(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_attachment_changing_async_view(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        logger.debug(_('\nSuccessfully finished test for asynchronous Changing views for all permutations of user roles, '
                'confidentiality levels and relevant models\n\n'))


class TristanTests(FunctionalTestCase):

    def test_AsyncGetPersonsView(self):
        # Given there's a person record in the system
        person_record = Person.objects.create(name="ostreiculture")

        # When I query the persons ajax query endpoint by the name
        client = self.log_in(is_administrator=True)
        response = client.post(
            reverse('changing:async_get_persons'),
            {
                'searchCriteria': "ostreiculture",
            },
            content_type='application/json'
        )

        # Then I should get back a json response where the "data" key contains a list
        data = response.json()['data']
        self.assertEqual(
            type(data),
            type([])
        )
        # And the first item on the list should be a dictionary with the person's name
        self.assertEqual(
            f"ostreiculture (pk:{person_record.pk})",
            data[0]['label']
        )

    def test_AsyncGetPersonsView_invalid_request_data(self):
        # Given there's a person record in the system
        Person.objects.create(name="ostreiculture")

        # When I query the persons ajax query endpoint with an invalid search query
        client = self.log_in(is_administrator=True)
        response = client.post(
            reverse('changing:async_get_persons'),
            {
                'searchCriteria': "",
            },
            content_type='application/json'
        )

        # Then I should get back a json response with an error message
        self.assertEqual(
            'Could not retrieve persons. Please reload the page. No search criteria specified.',
            response.json()['error']
        )

    def test_AsyncGetPersonsView_no_results_found(self):
        # Given there are no person records in the system

        # When I query the persons ajax query endpoint with an invalid search query
        client = self.log_in(is_administrator=True)
        response = client.post(
            reverse('changing:async_get_persons'),
            {
                'searchCriteria': "Abracadabra",
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {},
            response.json()['data']
        )

    def test_jsonify_error(self):
        result = SecuredAsyncJsonView.jsonify_error(err="Exception message", b="Localized text preceding the error")
        self.assertEqual(
            result.error,
            'Localized text preceding the error Exception message.'
        )
