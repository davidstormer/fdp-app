from django.core.files.storage import default_storage
from data_wizard.loaders import FileLoader as DataWizardFileLoader
from itertable.loaders import FileLoader as IterableFileLoader
from itertable.util import guess_type, PARSERS, make_iter
from itertable.mappers import TupleMapper
from itertable.exceptions import ParseFailed
from io import StringIO, BytesIO, TextIOWrapper
from pathlib import Path


class FdpIterableFileLoader(IterableFileLoader):
    """ A wrapper that allows FDP bulk import files to be loaded from any storage backend, so that they can be wrapped
    as an iterable.

    """
    def load(self):
        """ Load the file with the default storage backend that is defined.

        Based on load(...) method defined in itertable.loaders.IterableFileLoader.

        :return: Nothing.
        """
        try:
            # open file using the default storage backend
            # if using AzureStorage class, then an instance of the AzureStorageFile class will be returned
            # see: https://github.com/jschneier/django-storages/blob/master/storages/backends/azure_storage.py
            with default_storage.open(self.filename, self.read_mode) as opened_file:
                # for files that are not intended to be opened in binary mode
                if 'b' not in self.read_mode or not self.binary:
                    # wrap in a text stream, since iterator expects strings and not bytes
                    # see https://docs.python.org/3/library/io.html#io.TextIOWrapper
                    self.file = TextIOWrapper(opened_file)
                # files intended to be opened in binary mode
                else:
                    self.file = opened_file
            self.empty_file = False
        except IOError:
            if self.binary:
                self.file = BytesIO()
            else:
                self.file = StringIO()
            self.empty_file = True


def load_fdp_import_file(filename, mapper=TupleMapper, options={}):
    """ Loads an FDP bulk import file from any storage backend, such as an Azure Storage account, so that it can be
    processed and imported through the Django Data Wizard package.

    See: https://github.com/wq/django-data-wizard

    Based on load_file(...) function defined in itertable.util.

    :param filename: Relative path for file.
    :param mapper: Mapper class to use.
    :param options: Dictionary of additional options.
    :return: Loaded file wrapped as an iterable.
    """
    mimetype = guess_type(filename)
    # MIME type was not recognized but filename is defined
    if mimetype is None and filename:
        file_extension = Path(filename).suffix.lower()
        # MIME type for .xlsx (Microsoft Excel 2007+ spreadsheet) files may not be defined in some environments
        if file_extension == '.xlsx':
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    # no appropriate parser for file
    if mimetype not in PARSERS:
        raise ParseFailed("Could not determine parser for %s" % mimetype)
    parser = PARSERS[mimetype]
    loader = FdpIterableFileLoader
    iter_class = make_iter(loader, parser, mapper)
    return iter_class(filename=filename, **options)


class FdpDataWizardFileLoader(DataWizardFileLoader):
    """ Class to load a file from any storage backend, such as an Azure Storage account, so that it can be processed
    and imported through the Django Data Wizard package.

    See: https://github.com/wq/django-data-wizard

    """
    def load_iter(self):
        """ Loads the file with a wrapper so that it can be imported row by row.

        Uses custom function that will open the file with the default storage backend that is defined.

        :return: File wrapped as an iterable.
        """
        options = self.load_iter_options()
        return load_fdp_import_file(self.file.name, options=options)
