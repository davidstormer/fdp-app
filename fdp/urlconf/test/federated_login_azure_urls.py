from django.urls import path
from fdp.urlconf.azure_urls import urlpatterns
from fdpuser.views import FederatedLoginTemplateView
from inheritable.models import AbstractUrlValidator


#: Used in tests where the Azure configuration settings are applied, AND there is also a requirement for the federated
# login page.
urlpatterns += [
    path(AbstractUrlValidator.FDP_USER_FEDERATED_LOGIN_URL, FederatedLoginTemplateView.as_view(),
         name='federated_login')
]
