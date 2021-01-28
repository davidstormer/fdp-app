from django.utils.translation import gettext_lazy as _
from django.conf import settings
from inheritable.models import AbstractUrlValidator
from inheritable.views import SecuredSyncView
from .models import FdpImportFile


class DownloadImportFileView(SecuredSyncView):
    """ View that allows users to download an import file.

    """
    def get(self, request, path):
        """ Retrieve the requested import file.

        :param request: Http request object.
        :param path: Full path for the import file.
        :return: Import file to download.
        """
        if not path:
            raise Exception(_('No import file path was specified'))
        else:
            user = request.user
            # verify that user has import access
            if not user.has_import_access:
                raise Exception(_('Access is denied to import file'))
            # value that will be in import file's file field
            file_field_value = '{b}{p}'.format(b=AbstractUrlValidator.DATA_WIZARD_IMPORT_BASE_URL, p=path)
            # import file filtered for whether it exists
            unfiltered_queryset = FdpImportFile.objects.all()
            # import file does not exist
            if file_field_value and not unfiltered_queryset.filter(file=file_field_value).exists():
                raise Exception(_('User does not have access to import file'))
            return self.serve_static_file(
                request=request,
                path=path,
                absolute_base_url=settings.MEDIA_URL,
                relative_base_url=AbstractUrlValidator.DATA_WIZARD_IMPORT_BASE_URL,
                document_root=settings.MEDIA_ROOT
            )
