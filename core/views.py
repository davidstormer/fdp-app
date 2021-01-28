from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .models import PersonPhoto
from inheritable.models import AbstractUrlValidator
from inheritable.views import SecuredSyncView


class DownloadPersonPhotoView(SecuredSyncView):
    """ View that allows users to download a person photo file.

    """
    def get(self, request, path):
        """ Retrieve the requested person photo file.

        :param request: Http request object.
        :param path: Full path for the person photo file.
        :return: Person photo file to download.
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
            return self.serve_static_file(
                request=request,
                path=path,
                absolute_base_url=settings.MEDIA_URL,
                relative_base_url=AbstractUrlValidator.PERSON_PHOTO_BASE_URL,
                document_root=settings.MEDIA_ROOT
            )
