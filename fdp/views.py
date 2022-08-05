from django.views.generic import TemplateView

from inheritable.views import HostAdminSyncTemplateView


class BootstrapStyleGuide(HostAdminSyncTemplateView):
    template_name = 'bootstrap-style-guide.html'
