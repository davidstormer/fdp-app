from django.urls import re_path
from django.conf import settings
from inheritable.models import AbstractUrlValidator
from . import views


app_name = 'core'


urlpatterns = [
    re_path(
        r'{b}{s}(?P<path>.*)'.format(
            b=settings.MEDIA_URL[1:] if settings.MEDIA_URL.startswith('/') else settings.MEDIA_URL,
            s=AbstractUrlValidator.PERSON_PHOTO_BASE_URL
        ),
        view=views.DownloadPersonPhotoView.as_view(),
        name='download_person_photo'
    )
]
