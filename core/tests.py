from django.utils.translation import ugettext_lazy as _
from inheritable.models import AbstractUrlValidator
from inheritable.tests import AbstractTestCase, local_test_settings_required
from fdpuser.models import FdpOrganization, FdpUser
from .models import Person, PersonContact, PersonAlias, PersonPhoto, PersonIdentifier, PersonTitle, \
    PersonRelationship, PersonPayment, PersonGrouping, PersonIncident, GroupingIncident, Grouping, Incident
from supporting.models import PersonIdentifierType, Title, PersonRelationshipType
import logging

logger = logging.getLogger(__name__)


class CoreTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test for Admin Changelist, Create Instance, Change Instance, Delete Instance and History Views all permutations
    of user roles, confidentiality levels and relevant models:
            (A) Person has different levels of confidentiality
            (B) Incident has different levels of confidentiality

    (2) Test for Download PersonPhoto View for all permutations of user roles and confidentiality levels.

    """
    @classmethod
    def setUpTestData(cls):
        """ Create the categories that are necessary for typing the data to be created during tests.

        :return: Nothing.
        """
        if not PersonIdentifierType.objects.all().exists():
            PersonIdentifierType.objects.create(name='PersonIdentifierType1')
        if not Title.objects.all().exists():
            Title.objects.create(name='Title1')
        if not PersonRelationshipType.objects.all().exists():
            PersonRelationshipType.objects.create(name='PersonRelationshipType1')
        if not Grouping.objects.all().exists():
            Grouping.objects.create(name='Grouping1', **cls._is_law_dict)

    def setUp(self):
        """ Ensure data required for tests has been created.

        :return: Nothing.
        """
        # skip setup and tests unless configuration is compatible
        super().setUp()
        self.assertTrue(PersonIdentifierType.objects.all().exists())
        self.assertTrue(Title.objects.all().exists())
        self.assertTrue(Grouping.objects.all().exists())

    def __add_only_person_photos_data(self, fdp_org):
        """ Add person photos for persons with different confidential levels to the test database.

        :param fdp_org: FDP organization to use for some of the persons.
        :return: Dictionary containing unique names and primary keys for the person photos with different
        confidentiality levels.
        """
        self.assertEqual(Person.objects.all().count(), 0)
        person_photo_ids = {}
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
            person_photo_ids[name] = (
                PersonPhoto.objects.create(
                    photo='{b}{f}'.format(b=AbstractUrlValidator.PERSON_PHOTO_BASE_URL, f='dummy{i}.txt'.format(i=i)),
                    person=person
                )
            ).pk
        return person_photo_ids

    def __add_persons_related_data(self, fdp_org):
        """ Add persons with different confidential levels, and their related data, to the test database.

        :param fdp_org: FDP organization to use for some of the persons.
        :return: List of tuples including models and primary keys for instances referencing persons.
        """
        self.assertEqual(Person.objects.all().count(), 0)
        person_identifier_type = PersonIdentifierType.objects.all()[0]
        person_relationship_type = PersonRelationshipType.objects.all()[0]
        title = Title.objects.all()[0]
        grouping = Grouping.objects.all()[0]
        # create data without restrictions
        unrestricted_person = Person.objects.create(name='Name1', **self._is_law_dict, **self._not_confidential_dict)
        unrestricted_person_link_dict = {'person': unrestricted_person}
        unrestricted_person_contact = PersonContact.objects.create(**unrestricted_person_link_dict)
        unrestricted_person_alias = PersonAlias.objects.create(name='Alias1', **unrestricted_person_link_dict)
        num_of_photos = PersonPhoto.objects.all().count()
        unrestricted_person_photo = PersonPhoto.objects.create(
            photo='/y{i}.jpg'.format(i=num_of_photos), **unrestricted_person_link_dict
        )
        unrestricted_person_identifier = PersonIdentifier.objects.create(
            identifier='0123456', person_identifier_type=person_identifier_type, **unrestricted_person_link_dict
        )
        unrestricted_person_title = PersonTitle.objects.create(title=title, **unrestricted_person_link_dict)
        another_unrestricted_person = Person.objects.create(
            name='Name2', **self._is_law_dict, **self._not_confidential_dict
        )
        unrestricted_person_relationship = PersonRelationship.objects.create(
            subject_person=unrestricted_person, object_person=another_unrestricted_person, type=person_relationship_type
        )
        unrestricted_person_payment = PersonPayment.objects.create(**unrestricted_person_link_dict)
        unrestricted_person_grouping = PersonGrouping.objects.create(grouping=grouping, **unrestricted_person_link_dict)
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        unrestricted_person_incident = PersonIncident.objects.create(
            incident=unrestricted_incident, **unrestricted_person_link_dict
        )
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        person_ids = {}
        person_contact_ids = {}
        person_alias_ids = {}
        person_photo_ids = {}
        person_identifier_ids = {}
        person_title_ids = {}
        person_relationship_ids = {}
        person_payment_ids = {}
        person_grouping_ids = {}
        person_incident_ids = {}
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
            restricted_person_link_dict = {'person': person}
            person_contact_ids[name] = (PersonContact.objects.create(**restricted_person_link_dict)).pk
            person_alias_ids[name] = (PersonAlias.objects.create(name='SomeAlias', **restricted_person_link_dict)).pk
            num_of_photos = PersonPhoto.objects.all().count()
            person_photo_ids[name] = (
                PersonPhoto.objects.create(photo='/y{i}.jpg'.format(i=num_of_photos), **restricted_person_link_dict)
            ).pk
            person_identifier_ids[name] = (
                PersonIdentifier.objects.create(
                    identifier='987654', person_identifier_type=person_identifier_type, **restricted_person_link_dict
                )
            ).pk
            person_title_ids[name] = (PersonTitle.objects.create(title=title, **restricted_person_link_dict)).pk
            # create other persons for relationships
            another_unrestricted_person = Person.objects.create(
                name='Name2', **self._is_law_dict, **self._not_confidential_dict
            )
            person_relationship_ids[name] = (
                PersonRelationship.objects.create(
                    subject_person=person, object_person=another_unrestricted_person, type=person_relationship_type
                )
            ).pk
            person_payment_ids[name] = (PersonPayment.objects.create(**restricted_person_link_dict)).pk
            person_grouping_ids[name] = (
                PersonGrouping.objects.create(grouping=grouping, **restricted_person_link_dict)
            ).pk
            unrestricted_incident = Incident.objects.create(description='Desc2', **self._not_confidential_dict)
            person_incident = PersonIncident.objects.create(
                incident=unrestricted_incident, **restricted_person_link_dict
            )
            person_incident_ids[name] = person_incident.pk
        return [
            (Person, person_ids, None),
            (PersonContact, person_contact_ids, unrestricted_person_contact.pk),
            (PersonAlias, person_alias_ids, unrestricted_person_alias.pk),
            (PersonPhoto, person_photo_ids, unrestricted_person_photo.pk),
            (PersonIdentifier, person_identifier_ids, unrestricted_person_identifier.pk),
            (PersonTitle, person_title_ids, unrestricted_person_title.pk),
            (PersonRelationship, person_relationship_ids, unrestricted_person_relationship.pk),
            (PersonPayment, person_payment_ids, unrestricted_person_payment.pk),
            (PersonGrouping, person_grouping_ids, unrestricted_person_grouping.pk),
            (PersonIncident, person_incident_ids, unrestricted_person_incident.pk),
        ]

    def __add_incidents_related_data(self, fdp_org):
        """ Add incidents with different confidential levels, and their related data, to the test database.

        :param fdp_org: FDP organization to use for some of the incidents.
        :return: List of tuples including models and primary keys for instances referencing incidents.
        """
        self.assertEqual(Incident.objects.all().count(), 0)
        grouping = Grouping.objects.all()[0]
        # create data without restrictions
        unrestricted_incident = Incident.objects.create(description='Desc1', **self._not_confidential_dict)
        unrestricted_incident_link_dict = {'incident': unrestricted_incident}
        unrestricted_grouping_incident = GroupingIncident.objects.create(
            grouping=grouping, **unrestricted_incident_link_dict
        )
        unrestricted_person = Person.objects.create(
            name='Name1', **self._is_law_dict, **self._not_confidential_dict
        )
        unrestricted_person_incident = PersonIncident.objects.create(
            person=unrestricted_person, **unrestricted_incident_link_dict
        )
        # create data with restrictions
        # dictionaries containing data with different confidentiality levels
        incident_ids = {}
        grouping_incident_ids = {}
        person_incident_ids = {}
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
            # connect incidents to data
            restricted_incident_link_dict = {'incident': incident}
            grouping_incident = GroupingIncident.objects.create(grouping=grouping, **restricted_incident_link_dict)
            grouping_incident_ids[name] = grouping_incident.pk
            # create person for person-incidents
            another_person = Person.objects.create(name='Name2', **self._is_law_dict, **self._not_confidential_dict)
            person_incident = PersonIncident.objects.create(person=another_person, **restricted_incident_link_dict)
            person_incident_ids[name] = person_incident.pk
        return [
            (Incident, incident_ids, None),
            (GroupingIncident, grouping_incident_ids, unrestricted_grouping_incident.pk),
            (PersonIncident, person_incident_ids, unrestricted_person_incident.pk),
        ]

    def __delete_only_persons_data(self):
        """ Removes all persons from the test database.

        :return: Nothing.
        """
        PersonPhoto.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Person.objects.all().count(), 0)

    def __delete_persons_related_data(self):
        """ Removes all persons and related data from the test database.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        Incident.objects.all().delete()
        PersonGrouping.objects.all().delete()
        PersonPayment.objects.all().delete()
        PersonRelationship.objects.all().delete()
        PersonTitle.objects.all().delete()
        PersonIdentifier.objects.all().delete()
        PersonPhoto.objects.all().delete()
        PersonAlias.objects.all().delete()
        PersonContact.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Person.objects.all().count(), 0)

    def __delete_incidents_related_data(self):
        """ Removes all incidents and related data from the test database.

        :return: Nothing.
        """
        PersonIncident.objects.all().delete()
        GroupingIncident.objects.all().delete()
        Incident.objects.all().delete()
        Person.objects.all().delete()
        self.assertEqual(Incident.objects.all().count(), 0)

    def __test_download_person_photo_view(self, fdp_org, other_fdp_org):
        """ Test for Download Person Photo View for all permutations of user roles and confidentiality levels.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add person photos with persons with different confidentiality levels
        person_photo_ids = self.__add_only_person_photos_data(fdp_org=fdp_org)
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
            # keyword arguments to expand as parameters into the check methods below
            check_params = {
                'fdp_user': fdp_user,
                'fdp_org': fdp_org,
                'id_map_dict': person_photo_ids,
                'view_name': 'core:download_person_photo',
                'model_to_download': PersonPhoto,
                'field_with_file': 'photo',
                'base_url': AbstractUrlValidator.PERSON_PHOTO_BASE_URL,
                'expected_err_str': 'User does not have access to person photo'
            }
            # check data for FDP user without FDP org
            self._print_download_view_start_without_org(model_txt='person photo', user_role=user_role)
            self._check_if_can_download(**check_params)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_download_view_start_with_right_org(model_txt='person photo', user_role=user_role)
            self._check_if_can_download(**check_params)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_download_view_start_with_wrong_org(model_txt='person photo', user_role=user_role)
            self._check_if_can_download(**check_params)
        # remove person photos with different confidentiality levels
        self.__delete_only_persons_data()

    def __test_person_admin_views(self, fdp_org, other_fdp_org):
        """ Test for Admin Changelist, Create Instance, Change Instance, Delete Instance and History Views all
        permutations of user roles, confidentiality levels and models linked to Person directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add persons with different confidentiality levels
        models = self.__add_persons_related_data(fdp_org=fdp_org)
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
            # keyword arguments to expand as parameters into the check methods below
            check_params = {
                'fdp_user': fdp_user,
                'fdp_org': fdp_org,
                'password': self._password,
                'related_text': 'person',
                'models_to_test': models
            }
            # check data for FDP user without FDP org
            self._print_changelist_start_without_org(model_txt='person', user_role=user_role)
            self._check_admin_change_list_views(models_where_data_never_appears=[], **check_params)
            self._print_create_instance_start_without_org(model_txt='person', user_role=user_role)
            self._check_admin_create_instance_views(models_where_data_never_appears=[Person], **check_params)
            self._print_load_change_instance_start_without_org(model_txt='person', user_role=user_role)
            self._load_admin_change_instance_views(**check_params)
            self._print_change_instance_start_without_org(model_txt='person', user_role=user_role)
            self._check_admin_change_instance_views(models_where_data_never_appears=[Person], **check_params)
            self._print_load_history_start_without_org(model_txt='person', user_role=user_role)
            self._load_admin_history_views(**check_params)
            self._print_load_delete_start_without_org(model_txt='person', user_role=user_role)
            self._load_admin_delete_views(**check_params)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changelist_start_with_right_org(model_txt='person', user_role=user_role)
            self._check_admin_change_list_views(models_where_data_never_appears=[], **check_params)
            self._print_create_instance_start_with_right_org(model_txt='person', user_role=user_role)
            self._check_admin_create_instance_views(models_where_data_never_appears=[Person], **check_params)
            self._print_load_change_instance_start_with_right_org(model_txt='person', user_role=user_role)
            self._load_admin_change_instance_views(**check_params)
            self._print_change_instance_start_with_right_org(model_txt='person', user_role=user_role)
            self._check_admin_change_instance_views(models_where_data_never_appears=[Person], **check_params)
            self._print_load_history_start_with_right_org(model_txt='person', user_role=user_role)
            self._load_admin_history_views(**check_params)
            self._print_load_delete_start_with_right_org(model_txt='person', user_role=user_role)
            self._load_admin_delete_views(**check_params)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changelist_start_with_wrong_org(model_txt='person', user_role=user_role)
            self._check_admin_change_list_views(models_where_data_never_appears=[], **check_params)
            self._print_create_instance_start_with_wrong_org(model_txt='person', user_role=user_role)
            self._check_admin_create_instance_views(models_where_data_never_appears=[Person], **check_params)
            self._print_load_change_instance_start_with_wrong_org(model_txt='person', user_role=user_role)
            self._load_admin_change_instance_views(**check_params)
            self._print_change_instance_start_with_wrong_org(model_txt='person', user_role=user_role)
            self._check_admin_change_instance_views(models_where_data_never_appears=[Person], **check_params)
            self._print_load_history_start_with_wrong_org(model_txt='person', user_role=user_role)
            self._load_admin_history_views(**check_params)
            self._print_load_delete_start_with_wrong_org(model_txt='person', user_role=user_role)
            self._load_admin_delete_views(**check_params)
        # remove persons with different confidentiality levels
        self.__delete_persons_related_data()

    def __test_incident_admin_views(self, fdp_org, other_fdp_org):
        """ Test for Admin Changelist, Create Instance, Change Instance, Delete Instance and History Views all
        permutations of user roles, confidentiality levels and models linked to Incident directly and indirectly.

        :param fdp_org: FDP organization that may be linked to users and data.
        :param other_fdp_org: Another FDP organization that may be linked to users and data.
        :return: Nothing
        """
        # add incidents with different confidentiality levels
        models = self.__add_incidents_related_data(fdp_org=fdp_org)
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
            # keyword arguments to expand as parameters into the check methods below
            check_params = {
                'fdp_user': fdp_user,
                'fdp_org': fdp_org,
                'password': self._password,
                'models_to_test': models,
                'related_text': 'incident',
            }
            # check data for FDP user without FDP org
            self._print_changelist_start_without_org(model_txt='incident', user_role=user_role)
            self._check_admin_change_list_views(models_where_data_never_appears=[], **check_params)
            self._print_create_instance_start_without_org(model_txt='incident', user_role=user_role)
            self._check_admin_create_instance_views(models_where_data_never_appears=[Incident], **check_params)
            self._print_load_change_instance_start_without_org(model_txt='incident', user_role=user_role)
            self._load_admin_change_instance_views(**check_params)
            self._print_change_instance_start_without_org(model_txt='incident', user_role=user_role)
            self._check_admin_change_instance_views(models_where_data_never_appears=[Incident], **check_params)
            self._print_load_history_start_without_org(model_txt='incident', user_role=user_role)
            self._load_admin_history_views(**check_params)
            self._print_load_delete_start_without_org(model_txt='incident', user_role=user_role)
            self._load_admin_delete_views(**check_params)
            # change FDP user's organization
            fdp_user.fdp_organization = fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changelist_start_with_right_org(model_txt='incident', user_role=user_role)
            self._check_admin_change_list_views(models_where_data_never_appears=[], **check_params)
            self._print_create_instance_start_with_right_org(model_txt='incident', user_role=user_role)
            self._check_admin_create_instance_views(models_where_data_never_appears=[Incident], **check_params)
            self._print_load_change_instance_start_with_right_org(model_txt='incident', user_role=user_role)
            self._load_admin_change_instance_views(**check_params)
            self._print_change_instance_start_with_right_org(model_txt='incident', user_role=user_role)
            self._check_admin_change_instance_views(models_where_data_never_appears=[Incident], **check_params)
            self._print_load_history_start_with_right_org(model_txt='incident', user_role=user_role)
            self._load_admin_history_views(**check_params)
            self._print_load_delete_start_with_right_org(model_txt='incident', user_role=user_role)
            self._load_admin_delete_views(**check_params)
            # change FDP user's organization
            fdp_user.fdp_organization = other_fdp_org
            fdp_user.full_clean()
            fdp_user.save()
            # check data for FDP user with FDP org
            self._print_changelist_start_with_wrong_org(model_txt='incident', user_role=user_role)
            self._check_admin_change_list_views(models_where_data_never_appears=[], **check_params)
            self._print_create_instance_start_with_wrong_org(model_txt='incident', user_role=user_role)
            self._check_admin_create_instance_views(models_where_data_never_appears=[Incident], **check_params)
            self._print_load_change_instance_start_with_wrong_org(model_txt='incident', user_role=user_role)
            self._load_admin_change_instance_views(**check_params)
            self._print_change_instance_start_with_wrong_org(model_txt='incident', user_role=user_role)
            self._check_admin_change_instance_views(models_where_data_never_appears=[Incident], **check_params)
            self._print_load_history_start_with_wrong_org(model_txt='incident', user_role=user_role)
            self._load_admin_history_views(**check_params)
            self._print_load_delete_start_with_wrong_org(model_txt='incident', user_role=user_role)
            self._load_admin_delete_views(**check_params)
        # remove incidents with different confidentiality levels
        self.__delete_incidents_related_data()

    def test_admin_views(self):
        """ Test for Admin Changelist, Create Instance, Change Instance, Delete Instance and History Views all
        permutations of user roles, confidentiality levels and relevant models.

        :return: Nothing
        """
        logger.debug(
            _('\nStarting test for Core Data Admin changelist, create instance, change instance, delete instance and '
              'history views for all permutations of user roles, confidentiality levels and relevant models')
        )
        fdp_org = FdpOrganization.objects.create(name='FdpOrganization1Core')
        other_fdp_org = FdpOrganization.objects.create(name='FdpOrganization2Core')
        self.__test_person_admin_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        self.__test_incident_admin_views(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        logger.debug(_('\nSuccessfully finished test for Core Data Admin changelist, create instance, change instance, '
                'delete instance and history views for all permutations of user roles, confidentiality levels and '
                'relevant models\n\n'))

    def test_download_person_photo_view(self):
        """ Test for Download Person Photo View for all permutations of user roles and confidentiality levels.

        :return: Nothing
        """
        logger.debug(_('\nStarting test for Download Person Photo view for all permutations of user roles and'
                ' confidentiality levels'))
        fdp_org = FdpOrganization.objects.create(name='FdpOrganizationDlPerPh1')
        other_fdp_org = FdpOrganization.objects.create(name='FdpOrganizationDlPerPh2')
        self.__test_download_person_photo_view(fdp_org=fdp_org, other_fdp_org=other_fdp_org)
        logger.debug(_('\nSuccessfully finished test for Download Person Photo view for all permutations of user roles and '
                'confidentiality levels\n\n'))
