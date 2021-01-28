from django.test import Client
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from bulk.models import BulkImport, FdpImportFile, FdpImportMapping
from inheritable.models import AbstractUrlValidator
from inheritable.tests import AbstractTestCase
from fdpuser.models import FdpUser, FdpOrganization


class BulkTestCase(AbstractTestCase):
    """ Performs following tests:

    (1) Test Bulk Import access is host-only

    """
    def setUp(self):
        """ Add "data wizard" package import file.

        :return: Nothing.
        """
        self._fdp_import_file = FdpImportFile.objects.create(
            file='{b}x.csv'.format(b=AbstractUrlValidator.DATA_WIZARD_IMPORT_BASE_URL)
        )

    def __check_if_can_download_fdp_import_file(self, fdp_user):
        """ Checks whether an Fdp Import File can be downloaded for a particular user.

        :param fdp_user: FDP user downloading Fdp Import File.
        :return: Nothing.
        """
        client = Client(REMOTE_ADDR='127.0.0.1')
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
        file_path = str(self._fdp_import_file.file)
        if file_path.startswith(AbstractUrlValidator.DATA_WIZARD_IMPORT_BASE_URL):
            file_path = file_path[len(AbstractUrlValidator.DATA_WIZARD_IMPORT_BASE_URL):]
        url = reverse('bulk:download_import_file', kwargs={'path': file_path})
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
            print(_('Fdp Import File download check is successful (file could be downloaded by host administrator)'))
        # guest admin
        else:
            print(_('Fdp Import File download check is successful (exception was raised for guest administrator)'))

    def test_bulk_import_host_only_access(self):
        """ Test that only host administrators can access bulk import.

        :return: Nothing
        """
        print(_('\nStarting test for bulk import access is host-only'))
        num_of_users = FdpUser.objects.all().count()
        host_admin = self._create_fdp_user(email_counter=num_of_users + 1, **self._host_admin_dict)
        guest_admin = self._create_fdp_user(email_counter=num_of_users + 2, **self._guest_admin_dict)
        guest_admin.fdp_organization = FdpOrganization.objects.create(name='FdpOrganization1Bulk')
        guest_admin.full_clean()
        guest_admin.save()
        # cycle through all models to test
        for model_to_test in [BulkImport, FdpImportFile, FdpImportMapping]:
            meta = getattr(model_to_test, '_meta')
            model_name = meta.model_name
            url = reverse('admin:{app}_{model_to_test}_changelist'.format(app=meta.app_label, model_to_test=model_name))
            test_dict = {'url': url, 'login_startswith': None}
            # test for guest administrator
            print('Starting host-only view access sub-test for {n} for guest administrator'.format(n=model_name))
            self._get_response_from_get_request(fdp_user=guest_admin, expected_status_code=403, **test_dict)
            # test for host administrator
            print('Starting host-only view access sub-test for {n} for host administrator'.format(n=model_name))
            self._get_response_from_get_request(fdp_user=host_admin, expected_status_code=200, **test_dict)
        # test downloading Fdp Import File for guest administrator
        self.__check_if_can_download_fdp_import_file(fdp_user=guest_admin)
        # test downloading Fdp Import File for host administrator
        self.__check_if_can_download_fdp_import_file(fdp_user=host_admin)
        print(_('\nSuccessfully finished test for bulk import access is host-only\n\n'))
