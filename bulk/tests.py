from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from bulk.models import BulkImport, FdpImportFile, FdpImportMapping, FdpImportRun
from inheritable.tests import AbstractTestCase, local_test_settings_required
from fdpuser.models import FdpUser, FdpOrganization
import logging

logger = logging.getLogger(__name__)


class BulkTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test Bulk Import access is host-only

    """
    def setUp(self):
        """ Add "data wizard" package import file.

        :return: Nothing.
        """
        # skip setup and tests unless configuration is compatible
        super().setUp()
        # create a bulk import file
        self._add_fdp_import_file()

    def __check_if_can_download_fdp_import_file(self, fdp_user):
        """ Checks whether an Fdp Import File can be downloaded for a particular user.

        :param fdp_user: FDP user downloading Fdp Import File.
        :return: Nothing.
        """
        client = Client(**self._local_client_kwargs)
        client.logout()
        two_factor = self._create_2fa_record(user=fdp_user)
        # log in user
        response = self._do_login(
            c=client,
            username=fdp_user.email,
            password=self._password,
            two_factor=two_factor,
            login_status_code=200,
            two_factor_status_code=200,
            will_login_succeed=True
        )
        url = reverse('bulk:download_import_file', kwargs={'path': self._get_fdp_import_file_file_path_for_view()})
        try:
            self._do_get(c=response.client, url=url, expected_status_code=404, login_startswith=None)
        except Exception as err:
            # guest admin
            if not fdp_user.is_host:
                self.assertEqual(str(err), 'Access is denied to import file')
            else:
                # we should never get here
                raise Exception(err)
        # host admin
        if fdp_user.is_host:
            logger.debug(_('Fdp Import File download check is successful (file could be downloaded by host administrator)'))
        # guest admin
        else:
            logger.debug(_('Fdp Import File download check is successful (exception was raised for guest administrator)'))

    @local_test_settings_required
    def test_bulk_import_host_only_access(self):
        """ Test that only host administrators can access bulk import.

        :return: Nothing
        """
        logger.debug(_('\nStarting test for bulk import access is host-only'))
        num_of_users = FdpUser.objects.all().count()
        host_admin = self._create_fdp_user(email_counter=num_of_users + 1, **self._host_admin_dict)
        guest_admin = self._create_fdp_user(email_counter=num_of_users + 2, **self._guest_admin_dict)
        guest_admin.fdp_organization = FdpOrganization.objects.create(name='FdpOrganization1Bulk')
        guest_admin.full_clean()
        guest_admin.save()
        # cycle through all models to test
        for model_to_test in [BulkImport, FdpImportFile, FdpImportMapping, FdpImportRun]:
            meta = getattr(model_to_test, '_meta')
            model_name = meta.model_name
            url = reverse('admin:{app}_{model_to_test}_changelist'.format(app=meta.app_label, model_to_test=model_name))
            test_dict = {'url': url, 'login_startswith': None}
            # test for guest administrator
            logger.debug('Starting host-only view access sub-test for {n} for guest administrator'.format(n=model_name))
            self._get_response_from_get_request(fdp_user=guest_admin, expected_status_code=403, **test_dict)
            # test for host administrator
            logger.debug('Starting host-only view access sub-test for {n} for host administrator'.format(n=model_name))
            self._get_response_from_get_request(fdp_user=host_admin, expected_status_code=200, **test_dict)
        # test downloading Fdp Import File for guest administrator
        self.__check_if_can_download_fdp_import_file(fdp_user=guest_admin)
        # test downloading Fdp Import File for host administrator
        self.__check_if_can_download_fdp_import_file(fdp_user=host_admin)
        logger.debug(_('\nSuccessfully finished test for bulk import access is host-only\n\n'))
