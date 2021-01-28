from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save
from django.utils.translation import ugettext_lazy as _


class BulkAppConfig(AppConfig):
    """ Configuration settings for bulk app.

    """
    name = 'bulk'
    verbose_name = _('Bulk Import & Upload')

    def ready(self):
        """ Connects pre/post-delete signals defined for the bulk app.

        :return: Nothing.
        """
        from .signals import post_delete_fdp_import_mapping, post_save_identifier, post_save_run
        from data_wizard.models import Identifier, Run
        # signal for after deleting an FDP import mapping
        post_delete.connect(post_delete_fdp_import_mapping, sender='bulk.FdpImportMapping')
        # signal for after saving an Identifier record
        post_save.connect(post_save_identifier, sender=Identifier)
        # signal for after saving a Run record
        post_save.connect(post_save_run, sender=Run)
