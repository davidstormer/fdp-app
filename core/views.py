from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .models import PersonPhoto
from inheritable.models import AbstractUrlValidator, AbstractConfiguration
from inheritable.views import SecuredSyncView
from django.http import HttpResponse
from pprint import pformat
from ipware import get_client_ip


class DEBUGShowHeaders(SecuredSyncView):

    def get(self, request):
        return HttpResponse(f"<pre>{pformat(get_client_ip(request, request_header_order=['HTTP_X_CLIENT_IP',]))} {pformat(request.META)}</pre>")


class DownloadPersonPhotoView(SecuredSyncView):
    """ View that allows users to download a person photo file.

    """
    def get(self, request, path):
        """ Retrieve the requested person photo file.

        :param request: Http request object.
        :param path: Full path for the person photo file.
        :return: Person photo file to download or link to download person photo.
        """
        if not path:
            raise Exception(_('No person photo path was specified'))
        else:
            user = request.user
            # value that will be in attachment's file field
            file_field_value = '{b}{p}'.format(b=AbstractUrlValidator.PERSON_PHOTO_BASE_URL, p=path)
            # person photos
            partially_filtered_queryset = PersonPhoto.active_objects.all()
            # person photos filtered for indirect confidentiality
            filtered_queryset = PersonPhoto.filter_for_admin(queryset=partially_filtered_queryset, user=user)
            # person photo is not accessible by user
            if file_field_value and not filtered_queryset.filter(photo=file_field_value).exists():
                raise Exception(_('User does not have access to person photo'))
            # if hosted in Microsoft Azure, storing person photos in an Azure Storage account is required
            if AbstractConfiguration.is_using_azure_configuration():
                return self.serve_azure_storage_static_file(name=file_field_value)
            # otherwise use default mechanism to serve files
            else:
                return self.serve_static_file(
                    request=request,
                    path=path,
                    absolute_base_url=settings.MEDIA_URL,
                    relative_base_url=AbstractUrlValidator.PERSON_PHOTO_BASE_URL,
                    document_root=settings.MEDIA_ROOT
                )
