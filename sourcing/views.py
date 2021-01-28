from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .models import Attachment
from inheritable.models import AbstractUrlValidator
from inheritable.views import SecuredSyncView


class DownloadAttachmentView(SecuredSyncView):
    """ View that allows users to download an attachment file.

    """
    def get(self, request, path):
        """ Retrieve the requested attachment file.

        :param request: Http request object.
        :param path: Full path for the attachment file.
        :return: Attachment file to download.
        """
        if not path:
            raise Exception(_('No attachment path was specified'))
        else:
            user = request.user
            # value that will be in attachment's file field
            file_field_value = '{b}{p}'.format(b=AbstractUrlValidator.ATTACHMENT_BASE_URL, p=path)
            # attachments filtered for direct confidentiality
            partially_filtered_queryset = Attachment.active_objects.all().filter_for_confidential_by_user(user=user)
            # attachments filtered for indirect confidentiality
            filtered_queryset = Attachment.filter_for_admin(queryset=partially_filtered_queryset, user=user)
            # attachment is not accessible by user
            if file_field_value and not filtered_queryset.filter(file=file_field_value).exists():
                raise Exception(_('User does not have access to attachment'))
            return self.serve_static_file(
                request=request,
                path=path,
                absolute_base_url=settings.MEDIA_URL,
                relative_base_url=AbstractUrlValidator.ATTACHMENT_BASE_URL,
                document_root=settings.MEDIA_ROOT
            )
