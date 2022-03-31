"""fdp URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from inheritable.models import AbstractConfiguration


# Configuration is for hosting in an Microsoft Azure environment.
from .views import BootstrapStyleGuide

if AbstractConfiguration.is_using_azure_configuration():
    from .urlconf.azure_urls import *
# Configuration is for hosting in a local development environment.
elif AbstractConfiguration.is_using_local_configuration():
    from .urlconf.local_urls import *
# Unknown configuration
else:
    urlpatterns = []

if settings.DEBUG is True:
    urlpatterns.append(
        path('bootstrap-style-guide', BootstrapStyleGuide.as_view())
    )