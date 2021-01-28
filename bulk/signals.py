from .models import FdpImportMapping, FdpImportRun
from data_wizard.models import Range, Identifier


def post_delete_fdp_import_mapping(sender, instance, using, **kwargs):
    """ Removes all data to which the FDP import mapping record was linked, including the Identifier record data and its
    corresponding Range records.

    :param sender: Always the FdpImportMapping model class.
    :param instance: Instance of the FdpImportMapping model class that was deleted.
    :param using: The database alias being used.
    :param kwargs: Additional keyword arguments.
    :return: Nothing.
    """
    # delete the ranges linked to the corresponding identifier
    ranges = Range.objects.filter(identifier=instance.identifier)
    ranges.delete()
    # delete the corresponding identifier
    identifier = Identifier.objects.filter(pk=instance.identifier.pk)
    identifier.delete()


def post_save_identifier(sender, instance, created, raw, using, update_fields, **kwargs):
    """ Creates an FDP import mapping record that corresponds to the newly created Identifier record.

    :param sender: Always the Identifier model class.
    :param instance: Instance of the Identifier model class that was saved.
    :param created: True if instance was created.
    :param raw: True if the model is saved exactly as presented (i.e. when loading a fixture). One should not
    query/modify other records in the database as the database might not be in a consistent state yet.
    :param using: The database alias being used.
    :param update_fields: The set of fields to update as passed to Model.save(), or None if update_fields wasn’t passed
    to save().
    :param kwargs: Additional keyword arguments.
    :return: Nothing.
    """
    # only create a new FDP import mapping record if a new Identifier record was just created.
    if created:
        fdp_import_mapping = FdpImportMapping(identifier=instance)
        fdp_import_mapping.full_clean()
        fdp_import_mapping.save()


def post_save_run(sender, instance, created, raw, using, update_fields, **kwargs):
    """ Creates an FDP import run record that corresponds to the newly created Run record.

    :param sender: Always the Run model class.
    :param instance: Instance of the Run model class that was saved.
    :param created: True if instance was created.
    :param raw: True if the model is saved exactly as presented (i.e. when loading a fixture). One should not
    query/modify other records in the database as the database might not be in a consistent state yet.
    :param using: The database alias being used.
    :param update_fields: The set of fields to update as passed to Model.save(), or None if update_fields wasn’t passed
    to save().
    :param kwargs: Additional keyword arguments.
    :return: Nothing.
    """
    # only create a new FDP import run record if a new Run record was just created.
    if created:
        fdp_import_run = FdpImportRun(run=instance)
        fdp_import_run.full_clean()
        fdp_import_run.save()
