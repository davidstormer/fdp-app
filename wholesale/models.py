from django.db import models, router
from django.db.models import Q, ManyToManyField, ForeignKey, OneToOneField, ManyToManyRel, ManyToOneRel, OneToOneRel
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError, FieldDoesNotExist
from django.core.files.base import ContentFile
from django.core import serializers
from django.apps import apps
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from django.conf import settings
from inheritable.models import Metable, AbstractUrlValidator, AbstractFileValidator, AbstractConfiguration, \
    AbstractStringValidator
from fdpuser.models import FdpUser
from bulk.models import BulkImport
from reversion.revisions import create_revision, force_str, _get_options, _get_content_type
from reversion.models import Revision, Version
from csv import reader as csv_reader, writer as csv_writer
from operator import attrgetter
from decimal import Decimal
from datetime import date, datetime
from json import loads as json_loads, dumps as json_dumps
from json.decoder import JSONDecodeError
from io import StringIO
from uuid import uuid4
from functools import reduce
from sys import exc_info
from os.path import basename, dirname
from codecs import BOM_UTF8
from ast import literal_eval
from collections import defaultdict


class ModelHelper(models.Model):
    """ Abstract class defining constants and methods used to load and process models from various apps.

    """
    #: Name of 'sourcing' app that contains relevant models.
    __sourcing_app_name = 'sourcing'

    #: Name of 'core' app that contains relevant models.
    __core_app_name = 'core'

    #: Name of 'supporting' app that contains relevant models.
    __supporting_app_name = 'supporting'

    #: Name of attribute storing model name as a string representation.
    __model_name_attribute = '__name__'

    @staticmethod
    def __get_model_options(model):
        """ Retrieves the options for a particular Django model.

        Uses the '_meta' attribute.

        :param model: Model for which to retrieve options.
        :return: Object representing options for model.
        """
        return getattr(model, '_meta')

    @staticmethod
    def __get_models(app):
        """ Retrieves a list of models for a specific app.

        :param app: App for which to retrieve list of models.
        :return: List of models for app.
        """
        return list(apps.get_app_config(app).get_models())

    @classmethod
    def __get_sourcing_models(cls):
        """ Retrieves list of models for 'sourcing' app.

        :return: List of models in 'sourcing' app.
        """
        return cls.__get_models(app=cls.__sourcing_app_name)

    @classmethod
    def __get_core_models(cls):
        """ Retrieves list of models for 'core' app.

        :return: List of models in 'core' app.
        """
        return cls.__get_models(app=cls.__core_app_name)

    @classmethod
    def __get_supporting_models(cls):
        """ Retrieves list of models for 'supporting' app.

        :return: List of models in 'supporting' app.
        """
        return cls.__get_models(app=cls.__supporting_app_name)

    @classmethod
    def get_str_for_cls(cls, model_class):
        """ Retrieves the string representation for a model class.

        :param model_class: Model class.
        :return: String representing model class.
        """
        return getattr(model_class, cls.__model_name_attribute)

    @classmethod
    def get_field(cls, model, field_name):
        """ Retrieves a field for a model.

        Raises StopWholesaleImportException if field does not exist.

        :param model: Model for which to retrieve a field.
        :param field_name: Name of field to retrieve.
        :return: Field for model.
        """
        try:
            return (cls.__get_model_options(model=model)).get_field(field_name)
        except FieldDoesNotExist as err:
            raise StopWholesaleImportException(err)

    @classmethod
    def get_fields(cls, model):
        """ Retrieves list of fields for a model.

        :param model: Model for which to retrieve list of fields.
        :return: List of fields for model.
        """
        return (cls.__get_model_options(model=model)).get_fields()

    @classmethod
    def get_relevant_models(cls):
        """ Retrieves list of all models from the sourcing, core and supporting apps.

        :return: List of models in 'sourcing', 'core', and 'supporting' apps.
        """
        return cls.__get_sourcing_models() + cls.__get_core_models() + cls.__get_supporting_models()

    @classmethod
    def get_app_name(cls, model):
        # check if model is in the sourcing app
        if model in map(attrgetter(cls.__model_name_attribute), cls.__get_sourcing_models()):
            app_name = cls.__sourcing_app_name
        # check if model is in the core app
        elif model in map(attrgetter(cls.__model_name_attribute), cls.__get_core_models()):
            app_name = cls.__core_app_name
        # check if model is in the supporting app
        elif model in map(attrgetter(cls.__model_name_attribute), cls.__get_supporting_models()):
            app_name = cls.__supporting_app_name
        else:
            app_name = None
        return app_name

    @classmethod
    def get_model_class(cls, app_name, model_name):
        """ Retrieves the class for a model in an app.

        :param app_name: Name of app.
        :param model_name: Name of model.
        :return: Class for model in app.
        """
        return apps.get_model(app_label=app_name, model_name=model_name)

    @staticmethod
    def is_field_linked_to_another_model(model, field):
        """ Checks whether a field that is declared on a model links to any other model.

        Many-to-many fields, foreign keys and one-to-one fields will be considered as long as they link to a model
        other than the one on which they are declared.

        :param model: Model on which field is declared.
        :param field: Field to check.
        :return: True if field links to a model that is different than the on on which it is declared, false otherwise.
        """
        return (
                # field for relation must be defined on the model itself
                (field.many_to_many and isinstance(field, ManyToManyField))
                or (field.many_to_one and isinstance(field, ForeignKey))
                or (field.one_to_one and isinstance(field, OneToOneField))
        ) and (
                # field cannot reference model it is defined on
                model != field.remote_field.model
        )

    @staticmethod
    def is_field_a_relation(field):
        """ Checks whether field is actually a relation, and so not a declared field.

        E.g., if Model A has a FK to Model B, then Model A has a FK field, and Model B has a many-to-one relation.

        :param field: Field for which to check.
        :return: True if field is actually a relation and not a declared field.
        """
        return field.is_relation and (
                isinstance(field, OneToOneRel) or isinstance(field, ManyToOneRel) or isinstance(field, ManyToManyRel)
        )

    class Meta:
        abstract = True


class EndedWithErrorsWholesaleImportException(Exception):
    """ Exception raised when a wholesale import process ended with errors.

    """
    pass


class StopWholesaleImportException(Exception):
    """ Exception raised to stop a wholesale import process.

    """
    pass


class SkipWholesaleImportRecord(Exception):
    """ Exception raised to skip importing a record during a wholesale import process.

    """


def handle_import_errors(func):
    """ Retrieves a decorator method that allows for the wrapping of an instance method in a try... except... block that
    handles import errors.

    :param func: Instance method that should be wrapped in try... except... block.
    :return: Decorator.
    """
    def decorator(*args, **kwargs):
        """ Decorator that wraps an instance method in a try... except... block that handles import errors.

        :param args: Positional arguments for decorated instance method, starting with a reference to the
        instance itself, i.e. "self".
        :param kwargs: Keyword arguments for decorated instance method.
        :return: Nothing.
        """
        self = args[0]
        try:
            func(*args, **kwargs)
        except StopWholesaleImportException as err:
            # exception was raised that was already handled to some degree
            self.finish_import_without_raising_exception(err=err)
            self.full_clean()
            self.save()
        except:
            # unhandled exception
            exc_type, exc_value, exc_traceback = exc_info()
            # cycle to the most specific call
            while exc_traceback.tb_next is not None:
                exc_traceback = exc_traceback.tb_next
            # line number of offending code
            line_number = exc_traceback.tb_lineno
            # file name in which offending code resides
            full_path = exc_traceback.tb_frame.f_code.co_filename
            filename = basename(full_path)
            app_name = basename(dirname(full_path))
            # class for exception
            exc_type_name = ModelHelper.get_str_for_cls(model_class=exc_type)
            self.finish_import_without_raising_exception(
                err=f'Unhandled exception of type: {exc_type_name}; with message: {exc_value}; '
                    f'on line number: {line_number}; in file: {filename}; and in app: {app_name}.'
            )
            self.full_clean()
            self.save()
    return decorator


class WholesaleImportManager(models.Manager):
    """ Manager for imports performed through the wholesale import tool.

    """
    pass


class WholesaleImport(Metable):
    """ Import of data adding to or updating the database through the wholesale import tool.

    Attributes:
        :created_timestamp (datetime): Automatically added timestamp recording when wholesale import was created.
        :started_timestamp (datetime): Timestamp recording when wholesale import was started.
        :ended_timestamp (datetime): Timestamp recording when wholesale import was ended.
        :action (str): The nature of the database change that is intended with the import such as add or update.
        :file (file): Template file containing data for wholesale import.
        :user (str): User starting import.
        :import_models (json): JSON formatted list of model names that were imported through the wholesale import.
        :import_errors (str): Errors, if any, that were encountered during the import.
        :import_rows (int): Number of rows that were imported.
        :error_rows (int): Number of rows where errors were encountered.
        :uuid (str): Random combination of characters that form a unique identifier for the import. Used to identify
        corresponding reversion records.

    Properties:
        :is_started (bool): True if wholesale import was started, false if it was created but not yet started.
        :is_ended (bool): True if wholesale import was ended, false if it was created and started but not yet ended.
        :is_ready_for_import (bool): True if record is ready for its data to be imported, false otherwise.
        :has_errors (bool): True if wholesale import encountered errors, false otherwise.
        :import_models_as_str (str): Retrieves the main models that were imported through this wholesale import as a
        single string.
        :is_add (bool): True if wholesale import is an "add" import, false otherwise.
        :is_update (bool): True if wholesale import is an "update" import, false otherwise.
    """
    #: A one-character string used to separate fields. It defaults to ','.
    csv_delimiter = ','

    #: A one-character string used to quote fields containing special characters, such as the delimiter or quotechar,
    # or which contain new-line characters. It defaults to '"'.
    csv_quotechar = '"'

    #: The encoding use for the CSV templates.
    csv_encoding = 'UTF-8'

    #: Tuple of values that represent True if the field is a boolean.
    true_booleans = ('true', 'yes', 'checked', 't', 'y')

    #: Tuple of values that represent False if the field is a boolean.
    false_booleans = ('false', 'no', 'unchecked', 'f', 'n')

    #: Expected format if the field is a date.
    # See: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    date_format = '%Y-%m-%d'

    #: Expected format if the field is a datetime.
    # See: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    datetime_format = f'{date_format} %H:%M:%S'

    #: A one-character string used to separate multiple values that are placed into one column for many-to-many fields.
    m2m_delimiter = ','

    #: An iterable that contains all possible values that represent an empty CSV cell.
    empty_cell_vals = (None, '')

    #: Categories used to type each column of a wholesale import.
    __external_pk_type = 0  # only external ID for database primary key, i.e. excludes any FKs, O2O, and M2M
    __bool_type = 1
    __int_type = 2
    __decimal_type = 3
    __str_type = 4
    __date_type = 5
    __datetime_type = 6
    __json_type = 7
    __m2m_rel_type = 8  # only many-to-many relation field
    __non_m2m_rel_type = 9  # only relation fields that are NOT many-to-many

    #: Value for add action option for import.
    add_value = 'A'

    #: Label for add action option for import.
    add_label = _('Add')

    #: Value for update action option for import.
    update_value = 'U'

    #: Label for update action option for import.
    update_label = _('Update')

    #: Choices for action intended during import such as add or update of data.
    action_choices = ((add_value, add_label,), (update_value, update_label,))

    #: Suffix added to database primary key field name to reference a record's external primary key.
    external_id_suffix = '__external'

    #: Length of UUID for wholesale imports.
    _uuid_len = 36

    #: Name of database primary key columns.
    _id_col = 'id'
    #: Name of external unique identifier columns.
    _id_external_col = f'{_id_col}{external_id_suffix}'

    created_timestamp = models.DateTimeField(
        null=False,
        blank=False,
        auto_now_add=True,
        help_text=_('Automatically added timestamp recording when batch was created.'),
        verbose_name=_('created timestamp'),
        db_index=True
    )

    started_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Timestamp recording when import of data was started.'),
        verbose_name=_('started timestamp'),
        db_index=True
    )

    ended_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Timestamp recording when import of data was ended.'),
        verbose_name=_('ended timestamp'),
        db_index=True
    )

    action = models.CharField(
        null=False,
        blank=False,
        choices=action_choices,
        max_length=1,
        verbose_name=_('Action'),
        help_text=_('The nature of the database change that is intended with the import such as add or update.'),
    )

    file = models.FileField(
        upload_to=f'{AbstractUrlValidator.WHOLESALE_BASE_URL}%Y/%m/%d/%H/%M/%S/',
        blank=False,
        null=False,
        validators=[
            AbstractFileValidator.validate_wholesale_file_size,
            AbstractFileValidator.validate_wholesale_file_extension
        ],
        max_length=AbstractFileValidator.MAX_WHOLESALE_FILE_LEN,
        verbose_name=_('File'),
        help_text=_(
            'Template file containing data for import. Should be less than {s}MB.'.format(
                s=AbstractFileValidator.get_megabytes_from_bytes(
                    num_of_bytes=AbstractConfiguration.max_wholesale_file_bytes()
                )
            )
        ),
        unique=True,
    )

    user = models.CharField(
        null=False,
        blank=False,
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('User'),
        help_text=_('User starting import.'),
    )

    import_models = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Models'),
        help_text=_('JSON formatted list of model names that were imported through the wholesale import.'),
    )

    import_errors = models.TextField(
        null=False,
        blank=True,
        verbose_name=_('Errors'),
        help_text=_('Errors, if any, that were encountered during the import.')
    )

    imported_rows = models.PositiveIntegerField(
        null=False,
        blank=False,
        default=0,
        verbose_name=_('Rows imported'),
        help_text=_('Number of rows that were imported.')
    )

    error_rows = models.PositiveIntegerField(
        null=False,
        blank=False,
        default=0,
        verbose_name=_('Rows with errors'),
        help_text=_('Number of rows where errors were encountered.')
    )

    uuid = models.CharField(
        null=False,
        blank=False,
        max_length=_uuid_len,
        validators=[MinLengthValidator(_uuid_len)],
        verbose_name=_('UUID'),
        help_text=_('Random combination of characters that form a unique identifier for the import. '
                    'Used to identify corresponding reversion records.'),
        unique=True
    )

    @property
    def has_errors(self):
        """ True if wholesale import encountered errors, false otherwise.

        :return: String representing full name for entity in database.
        """
        # either import-wide errors were encountered, or at least one row had an error
        if self.import_errors or self.error_rows > 0:
            return True
        else:
            return False

    @property
    def is_started(self):
        """ Checks whether the wholesale import was started.

        :return: True if wholesale import was started, false if it was created but not yet started.
        """
        return True if self.started_timestamp else False

    @property
    def is_ended(self):
        """ Checks whether the wholesale import was ended.

        :return: True if wholesale import was ended, false if it was created and started, but not yet ended.
        """
        return True if self.ended_timestamp else False

    @property
    def is_ready_for_import(self):
        """ Checks whether the data for this record is ready to be imported.

        Data is ready to be imported if:
            (1) No errors are already noted for this import; some could have been noted while converting implicit model
                references to explicit model references).
            (2) Import has not yet been started.
            (3) Import has not yet been ended.

        :return: True if the data is ready to be imported, false otherwise.
        """
        return not (self.is_started or self.is_ended or self.has_errors)

    @property
    def import_models_as_str(self):
        """ Retrieves the main models that were imported through this wholesale import as a single string.

        :return: Single string representing imported main models.
        """
        return '' if not self.import_models else ', '.join(self.import_models)

    @property
    def is_add(self):
        """ Checks whether this record is an "add" import.

        :return: True if this record is an "add" import, false otherwise.
        """
        return self.action == self.add_value

    @property
    def is_update(self):
        """ Checks whether this record is an "update" import.

        :return: True if this record is an "update" import, false otherwise.
        """
        return self.action == self.update_value

    objects = WholesaleImportManager()

    #: Keys and static indexes used to access metadata and data that was prepared for the import.
    #: Used in _metadata_by_col_index
    __model_name_index = 0
    __field_name_index = 1
    __field_type_index = 2
    __rel_model_name_index = 3
    #: Used in _metadata_by_model_name
    __model_class_index = 0
    __model_fields_index = 1
    #: Used in _data_by_model_name for each model instance
    __instance_attr_dict_index = 0
    __instance_external_id_index = 1
    __instance_m2m_index = 2
    #: Used in _data_by_model_name for each model instance's many-to-many field names and values.
    __m2m_field_name_index = 0
    __m2m_field_values_index = 1
    #: Used in _by_name_non_m2m_rel_data_by_model_name, _by_external_id_non_m2m_rel_data_by_model_name,
    #: _by_name_m2m_rel_data_by_model_name and _by_external_id_m2m_rel_data_by_model_name.
    __data_row_index = 0
    __actual_field_name_index = 1
    #: Used in _m2m_metadata_by_model_name for each many-to-many field for each defining model.
    __through_pk_index = 0
    __through_fk_index = 1
    __through_model_class_index = 2

    def __add_to_metadata_by_col_index(self, model_name, field_name, field_type, rel_model_name):
        """ Adds a tuple to the metadata for the import whose data structure corresponds to the list of column indices
        in the data.

        If changing, update __model_name_index, __field_name_index, __field_type_index and __rel_model_name_index.

        :param model_name: Name of model that is referenced by the column.
        :param field_name: Name of field that is referenced by the column.
        :param field_type: Wholesale import categorization for type of field that is referenced by the column.
        See __bool_type, __int_type, etc.
        :param rel_model_name: Name of model that may be linked in by the relation field that is referenced by
        the column. Will be None for fields that are not relations.
        :return: Nothing.
        """
        self._metadata_by_col_index.append((model_name, field_name, field_type, rel_model_name))

    def __add_to_metadata_by_model_name(self, model_name, model_class, model_fields):
        """ Adds a tuple to the metadata for the import whose data structure is a dictionary where the keys are string
        representations of model names.

        If changing, update __model_class_index and __model_fields_index.

        :param model_name: String representation of model name.
        :param model_class: Class defining model.
        :param model_fields: Tuple of fields that define import for model. Only used for updates. Ignored for adds.
        :return: Nothing.
        """
        self._metadata_by_model_name[model_name] = (model_class, model_fields)

    def __add_to_metadata_by_rel_model_name(self, rel_model_name, rel_model_class):
        """ Adds the model class referenced by a relation field such as an FK, O2O or M2M, to the metadata for the
        import whose data structure is a dictionary where the keys are string representations of the relation model
        names.

        :param rel_model_name: Name of model class referenced by a relation field.
        :param rel_model_class: Class defining model referenced by a relation field.
        :return: Nothing.
        """
        # only add relation, if it does not already exist
        if rel_model_name not in self._metadata_by_rel_model_name:
            self._metadata_by_rel_model_name[rel_model_name] = rel_model_class

    def __add_to_m2m_metadata_by_model_name(self, model_name, field_name, rel_model_name, through_model_class):
        """ Adds a tuple defining a many-to-many field to the metadata for the import whose data structure is a
        dictionary where keys are string representations of model names

        If changing, update __through_pk_index, __through_fk_index and __through_model_class_index.

        :param model_name: String representation of model declaring many-to-many field.
        :param field_name: String representation of many-to-many field.
        :param rel_model_name: String representation of model referenced through many-to-many field.
        :return: Nothing.
        """
        # main model is not yet in the dictionary
        if model_name not in self._m2m_metadata_by_model_name:
            self._m2m_metadata_by_model_name[model_name] = {}
        # many-to-many field not yet recorded for main model in dictionary
        if field_name not in self._m2m_metadata_by_model_name[model_name]:
            self._m2m_metadata_by_model_name[model_name][field_name] = (
                f'{model_name.lower()}_id',
                f'{rel_model_name.lower()}_id',
                through_model_class
            )

    @staticmethod
    def __get_data_for_m2m_in_data_by_model_name(field_name, field_values):
        """ Retrieves a tuple that contains the name of a many-to-many field, and its corresponding values. This tuple
        can be either appended to the list of many-to-many tuples in the _data_by_model_name data structure, or if the
        field name already exists, then its field values can be appended to the existing field values.

        If changing, update __m2m_field_name_index and __m2m_field_values_index.

        :param field_name: Name of many-to-many field.
        :param field_values: List of values for many-to-many field.
        :return: A tuple:
                    [0] Name of many-to-many field; and
                    [1] List of values for many-to-many field.
        """
        return field_name, field_values

    def __add_to_data_by_model_name(self, model_name, instance_attr_dic, instance_external_id, instance_m2ms, errors):
        """ If errors occurred then adds a list of errors, otherwise adds a tuple, to the data prepared for the import
        whose data structure is a dictionary where the keys are string representations of model names.

        If changing, update __instance_attr_dict_index, __instance_external_id_index and __instance_m2m_index.

        :param model_name: String representation of model name.
        :param instance_attr_dic: Dictionary that contains attributes and their values as key/value pairs to define
        the model instance that is ready for import.
        :param instance_external_id: Unique external identifier for model instance outside database; None otherwise.
        :param instance_m2ms: List of many-to-many field/values tuples.
        Use __get_data_for_m2m_in_data_by_model_name(...) to generate tuples.
        :param errors: List of errors that occurred during data preparation; None if no errors occurred.
        :return: Nothing.
        """
        # main model is not yet in dictionary
        if model_name not in self._data_by_model_name:
            self._data_by_model_name[model_name] = []
        # no errors were encountered while preparing this data
        if not errors:
            (self._data_by_model_name[model_name]).append((instance_attr_dic, instance_external_id, instance_m2ms))
        else:
            (self._data_by_model_name[model_name]).append(errors)

    def __add_to_by_external_id_rel_data_by_model_name(
            self, is_m2m, model_name, rel_model_name, external_id, row_num, actual_field_name
    ):
        """ Adds a tuple to the relation data prepared for the import and referenced by external ID, whose data
        structure is a dictionary where the keys are string representations of model names.

        If changing, updating __data_row_index and __actual_field_name_index.

        Uses one data structure for many-to-many fields and another data structure for foreign keys and one-to-one
        fields.

        :param is_m2m: True if relation data is many-to-many, false otherwise.
        :param model_name: String representation of main model name.
        :param rel_model_name: String representation of relation model name.
        :param external_id: External ID used to reference relation model instance.
        :param row_num: Index of row number in the CSV template file, starting at 0.
        :param actual_field_name: Actual field name in main model that references the relation model.
        :return: Nothing.
        """
        data_struct_name = '_by_external_id_non_m2m_rel_data_by_model_name' if not is_m2m \
            else '_by_external_id_m2m_rel_data_by_model_name'
        data_struct = getattr(self, data_struct_name)
        # relation model is not yet in dictionary
        if rel_model_name not in data_struct:
            data_struct[rel_model_name] = {}
        # external id is not yet in dictionary for that relation model
        if external_id not in data_struct[rel_model_name]:
            data_struct[rel_model_name][external_id] = {}
        # main model is not yet in dictionary for that external id for that relation model
        if model_name not in data_struct[rel_model_name][external_id]:
            data_struct[rel_model_name][external_id][model_name] = []
        # save index for instance of main model and referencing field name that will be updated as relation models
        # referenced by external IDs are evaluated and/or imported
        data_struct[rel_model_name][external_id][model_name].append((row_num, actual_field_name))

    def __add_to_by_name_rel_data_by_model_name(
            self, is_m2m, model_name, rel_model_name, named_instance, row_num, actual_field_name
    ):
        """ Adds a tuple to the relation data prepared for the import and referenced by a name value, whose data
        structure is a dictionary where the keys are string representations of model names.

        If changing, updating __data_row_index and __actual_field_name_index.

        Uses one data structure for many-to-many fields and another data structure for foreign keys and one-to-one
        fields.

        :param is_m2m: True if relation data is many-to-many, false otherwise.
        :param model_name: String representation of main model name.
        :param rel_model_name: String representation of relation model name.
        :param named_instance: Name, i.e. string, that is used to reference relation model instance.
        :param row_num: Index of row number in the CSV template file, starting at 0.
        :param actual_field_name: Actual field name in main model that references the relation model.
        :return: Nothing.
        """
        data_struct_name = '_by_name_non_m2m_rel_data_by_model_name' if not is_m2m \
            else '_by_name_m2m_rel_data_by_model_name'
        data_struct = getattr(self, data_struct_name)
        # relation model is not yet in dictionary
        if rel_model_name not in data_struct:
            data_struct[rel_model_name] = {}
        # name value is not yet in dictionary for that relation model
        if named_instance not in data_struct[rel_model_name]:
            data_struct[rel_model_name][named_instance] = {}
        # main model is not yet in dictionary for that name value for that relation model
        if model_name not in data_struct[rel_model_name][named_instance]:
            data_struct[rel_model_name][named_instance][model_name] = []
        # save index for instance of main model and referencing field name that will be updated as relation models
        # referenced by name values are evaluated and/or imported
        data_struct[rel_model_name][named_instance][model_name].append((row_num, actual_field_name))

    def __init_data_structures(self):
        """ Initializes data structures for metadata about the import such as the models to be imported, their fields,
        and those fields' types.

        Also initializes revision record placeholder for import.

        :return: Nothing.
        """
        # Stores metadata for the import in list format where the index of each list item corresponds to the index of
        # each column.
        # Use __model_name_index, __field_name_index, __field_type_index and __rel_model_name_index to access tuple
        # values.
        # In the format of: [
        #     (model_name_1, field_name_11, field_type_11, rel_model_name_11),
        #     (model_name_1, field_name_12, field_type_12, rel_model_name_12),
        #     ...
        #     (model_name_2, field_name_21, field_type_21, rel_model_name_21),
        #     (model_name_2, field_name_22, field_type_22, rel_model_name_22),
        #     ...
        # ]
        self._metadata_by_col_index = []
        # Stores metadata for the import in dictionary format where keys are string representations of model names.
        # Use __model_class_index and __model_fields_index to access tuple values.
        # In the format of: {
        #     'model_name_1': (model_class_1, model_fields_1),
        #     'model_name_2': (model_class_2, model_fields_2),
        #     ...
        # }
        self._metadata_by_model_name = {}
        # Stores metadata for the import in dictionary format where keys are string representations of relation model
        # names, i.e. for models that are referenced by relation fields such as FKs, O2Os and M2Ms.
        # In the format of: { 'rel_model_name_1': rel_model_class_1, 'rel_model_name_2': rel_model_class_2, ... }
        self._metadata_by_rel_model_name = {}
        # Stores metadata for the import in dictionary format where keys are string representations of model names.
        # Use __through_pk_index, __through_fk_index, and __through_model_class_index.
        # In the format of: {
        #     'model_name_1': {
        #         'field_name_1A': (through_model_pk_field_1A, through_model_fk_field_1A, through_model_class_1A),
        #         'field_name_1B': (through_model_pk_field_1B, through_model_fk_field_1B, through_model_class_1B),
        #         ...
        #     },
        #     model_name_2: { ... },
        #     ...
        # }
        self._m2m_metadata_by_model_name = {}
        # Stores data prepared for import in dictionary format where keys are string representations of model names.
        # Model instances that are ready for import will be represented by tuples.
        # Model instances whose preparation resulted in errors will be represented by lists.
        # Use __instance_attr_dict_index, __instance_external_id_index and __instance_m2m_index to access a model
        # instance's tuple values.
        # Use __m2m_field_name_index and __m2m_field_values_index to access a model instance's many-to-many tuple
        # values.
        # In the format of: {
        #     'model_name_1': [
        #         (
        #             instance_1a,
        #             'external_id_1a',
        #             [
        #                 (m2m_field_J, [m2m_field_J_id_1, m2m_field_J_id_2, ...]),
        #                 (m2m_field_V, [m2m_field_V_id_1, ...]),
        #                 ...
        #             ]
        #         ),  #: NOTE: item represents instance to add/update
        #         (instance_2b, external_id_1b, []),
        #         ...
        #     ],
        #     'model_name_2': [
        #         (instance_2a, 'external_id_2a', [(m2m_field_J, [m2m_field_J_id_1]),
        #         [error, another_error],  #: NOTE: item represents error
        #         ...
        #     ],
        #     ...
        # }
        self._data_by_model_name = {}
        # Stores relation data prepared for import in dictionary format where keys are string
        # representations of relation model names. Relevant only for relation data referenced using "by name"
        # references. One data structure stores many-to-many relation data, while the other data structure stores
        # relation data for foreign keys and one-to-one fields.
        # Use __data_row_index and __actual_field_name_index to access tuple values.
        # In the format of: {
        #     'rel_model_name_1': {
        #         'rel_model_instance_name_11': {
        #             'model_name_111': [
        #                 (instance_index_1111, instance_field_name_1111),
        #                 (instance_index_1112, instance_field_name_1112),
        #                 ...
        #             ],
        #             'model_name_112': [...]
        #             ...
        #         },
        #         'rel_model_instance_name_12: {
        #         },
        #         ...
        #     },
        #     rel_model_name_2': { ... },
        #     ...
        # }
        self._by_name_non_m2m_rel_data_by_model_name = {}
        self._by_name_m2m_rel_data_by_model_name = {}
        # Stores relation data prepared for import in dictionary format where keys are string
        # representations of relation model names. Relevant only for relation data referenced using "by external ID"
        # references. One data structure stores many-to-many relation data, while the other data structure stores
        # relation data for foreign keys and one-to-one fields.
        # Use __data_row_index and __actual_field_name_index to access tuple values.
        # In the format of: {
        #     'rel_model_name_1': {
        #         'rel_model_instance_external_id_11': {
        #             'model_name_111': [
        #                 (instance_index_1111, instance_field_name_1111),
        #                 (instance_index_1112, instance_field_name_1112),
        #                 ...
        #             ],
        #             'model_name_112': [...]
        #             ...
        #         },
        #         'rel_model_instance_external_id_12: {
        #         },
        #         ...
        #     },
        #     rel_model_name_2': { ... },
        #     ...
        # }
        self._by_external_id_non_m2m_rel_data_by_model_name = {}
        self._by_external_id_m2m_rel_data_by_model_name = {}
        # Groups revision records for import for the django-reversion package. Set in __add_revision_to_database(...).
        self._revision = None
        #  Stores the number of data rows that appear in the template. Will only be defined during the conversion of
        # implicit model references, i.e. in convert_implicit_references(...).
        self._num_of_data_rows = None

    def __init__(self, *args, **kwargs):
        """ Initializes data structures for metadata about the import such as the models to be imported, their fields,
        and those fields' types.

        Also initializes revision record placeholder for import.

        """
        super().__init__(*args, **kwargs)
        self.__init_data_structures()

    def __str__(self):
        """ Defines string representation for an import performed through the wholesale import tool.

        :return: String representation for an import performed through the wholesale import tool.
        """
        return f'{self.get_verbose_name()} #{self.pk}'

    def clean(self):
        """ Ensure that the wholesale import file path contains no directory traversal.

        :return: Nothing
        """
        super(WholesaleImport, self).clean()
        # full path when relative and root paths are joined
        full_path = AbstractFileValidator.join_relative_and_root_paths(
            relative_path=self.file,
            root_path=settings.MEDIA_ROOT
        )
        # verify that path is a real path (i.e. no directory traversal takes place)
        # will raise exception if path is not a real path
        AbstractFileValidator.check_path_is_expected(
            relative_path=self.file,
            root_path=settings.MEDIA_ROOT,
            expected_path_prefix=full_path,
            err_msg=_('Wholesale import file path may contain directory traversal'),
            err_cls=ValidationError
        )

    def __get_decoded_string_content(self):
        """ Retrieves the decoded string content of the CSV template.

        :return: String representing content in file.
        """
        file = getattr(self, 'file')
        # ensure that file handle offset is always at the beginning before reading
        self.__rewind_io(io_to_rewind=file)
        return file.read().decode(self.csv_encoding)

    @staticmethod
    def __rewind_io(io_to_rewind):
        """ Places current offset for the file handle or stream position back to the beginning.

         Can be used with a memory stream such as io.StringIO, with Django's FieldFile proxy, or similar.

        :param io_to_rewind: Instance to rewind.
        :return: Nothing.
        """
        io_to_rewind.seek(0)

    def __get_csv_reader(self, string_io):
        """ Retrieves the reader object used to read the CSV template.

        :param string_io: Instantiated StringIO instance that wraps the decoded string content of the CSV template.
        :return: Instantiated CSV reader object.
        """
        return csv_reader(string_io, delimiter=self.csv_delimiter, quotechar=self.csv_quotechar)

    def __get_csv_writer(self, string_io):
        """ Retrieves the writer object used to write the CSV template.

        :param string_io: Instantiated StringIO instance that is used as a buffer holding the content to write.
        :return: Instantiated CSV writer object.
        """
        return csv_writer(string_io, delimiter=self.csv_delimiter, quotechar=self.csv_quotechar)

    @classmethod
    def get_uuid(cls):
        """ Retrieves a UUID, a randomly generated unique identifier, to be used by a wholesale import model instance.

        :return: Nothing.
        """
        # maximum number of tries to generate unique identifier
        max_tries = 10
        # random UUID, see: https://docs.python.org/3/library/uuid.html#uuid.uuid4
        uuid = uuid4()
        tries = 1
        # keep trying to generate unique identifier until successful or max tries are exceeded
        while tries <= max_tries and cls.objects.filter(uuid=uuid).exists():
            uuid = uuid4()
            tries += 1
        # max tries were exceeded, so was not successful in generating unique identifier
        if tries > max_tries:
            raise Exception(f'UUID could not be generated for wholesale import')
        return uuid

    def __add_to_import_errors(self, err):
        """ Adds to the model instance's import errors field.

        :param err: Error that should be added.
        :return: Nothing.
        """
        # only if exception is defined
        if err:
            str_err = err.strip() if isinstance(err, str) else str(err).strip()
            # exception is still defined after stripping superfluous whitespace
            if str_err:
                # add ending period
                if not str_err.endswith('.'):
                    str_err = f'{str_err}.'
                # no errors previously defined
                if not self.import_errors:
                    self.import_errors = str_err
                # append error to other existing errors
                else:
                    # strip all superfluous whitespace
                    import_errors = self.import_errors.strip() if isinstance(self.import_errors, str) \
                        else str(self.import_errors).strip()
                    # add ending period
                    if import_errors and not import_errors.endswith('.'):
                        import_errors = f'{import_errors}.'
                    # append error
                    self.import_errors = f'{import_errors} {str_err}'

    def finish_import_without_raising_exception(self, err):
        """ Finishes the import by recording its errors, if any, and then DOES NOT raise an exception.

        :param err: Optional exception that may have been encountered.
        :return: Nothing.
        """
        self.ended_timestamp = now()
        self.__add_to_import_errors(err=err)

    def __finish_import_and_raise_exception(self, err):
        """ Finishes the import by recording its errors, if any, and then DOES raise
        a StopWholesaleImportException exception.

        :param err: Exception that was encountered.
        :return: Nothing.
        """
        self.finish_import_without_raising_exception(err=err)
        raise StopWholesaleImportException()

    def __get_field_metadata(self, field_name, model_name, model_class):
        """ Retrieves metadata for a model field which is used during the wholesale import.

        :param field_name: Name of field, as string.
        :param model_name: Name of model, in which field is declared, as string.
        :param model_class: Class defining model, in which field is declared, as string.
        :return: A tuple:
                    [0] Categorization for field, such as __bool_type, __int_type, etc.; and
                    [1] Class defining model referenced by field if the field is a relation, or None otherwise.
        """
        # relation fields that reference external IDs won't exist
        actual_field_name = field_name[:-len(self.external_id_suffix)] \
            if field_name.endswith(self.external_id_suffix) else field_name
        field = ModelHelper.get_field(model=model_class, field_name=actual_field_name)
        # wholesale import categorization for field, see __bool_type, __int_type, etc.
        column_type = None
        # model class referenced by field if it is a relation, will be None for non-relation fields
        rel_model_class = None
        # external ID for this particular record, i.e. not for a relation such as FK, O2O or M2M
        if field_name == f'id{self.external_id_suffix}':
            column_type = self.__external_pk_type
        else:
            # boolean fields
            if isinstance(field, (models.BooleanField,)):
                column_type = self.__bool_type
            # int fields
            elif isinstance(field, (models.BigIntegerField, models.PositiveBigIntegerField, models.IntegerField,
                                    models.PositiveIntegerField, models.SmallIntegerField)):
                column_type = self.__int_type
            # str fields
            elif isinstance(field, (models.CharField, models.EmailField, models.FileField, models.ImageField,
                                    models.SlugField, models.TextField, models.URLField, models.UUIDField)):
                column_type = self.__str_type
            # decimal fields
            elif isinstance(field, (models.DecimalField,)):
                column_type = self.__decimal_type
            # date fields
            elif isinstance(field, (models.DateField,)):
                column_type = self.__date_type
            # datetime fields
            elif isinstance(field, (models.DateTimeField,)):
                column_type = self.__datetime_type
            # json fields
            elif isinstance(field, (models.JSONField,)):
                column_type = self.__json_type
            # many-to-many relation fields
            elif isinstance(field, (models.ManyToManyField,)):
                column_type = self.__m2m_rel_type
                rel_model_class = field.remote_field.model
            # relation fields
            elif isinstance(field, (models.ForeignKey, models.OneToOneField)):
                column_type = self.__non_m2m_rel_type
                rel_model_class = field.remote_field.model
            # field is unrecognized, e.g. DurationField, FloatField, AutoField
            else:
                self.__finish_import_and_raise_exception(
                    err=f'Field {field_name} on model {model_name} is a type of field '
                        f'that is not yet supported through wholesale import.'
                )
        return column_type, rel_model_class

    def __parse_template_heading(self, heading):
        """ Parses out a CSV template heading into a model name and model field.

        :param heading: CSV template heading to parse.
        :return: A tuple:
                    [0] The name of the model; and
                    [1] The name of the field.
        """
        # heading will be in the form of Model.field such as Person.is_archived
        split_heading = heading.split('.')
        if len(split_heading) != 2:
            self.__finish_import_and_raise_exception(
                err=f'Column {heading} is not in the expected format of <Model.field>.'
            )
        model_name = split_heading[0]
        field_name = split_heading[1]
        return model_name, field_name

    def __make_import_metadata(self, reader):
        """ Creates and populates the data structures that contain metadata about the import such as the models, their
        fields and those fields' types.

        :param reader: Instantiated reader object from the csv module that allows for iterating over the CSV file.
        :return: Nothing.
        """
        headings_row = next(reader, None)
        if headings_row is None:
            self.__finish_import_and_raise_exception(err='No rows were found in CSV file.')
        # cache used only in this method to map model names to their respective model classes
        cached_model_classes = {}
        # list of fields for each model
        model_fields = []
        # will be used for the model instance's 'import_models' field
        import_models = []
        # total number of columns in CSV
        num_of_cols = len(headings_row)
        # list of already parsed headings that is used to identify duplicate headings, in the format of:
        # ['model1__field1', 'model1__field2', ... 'model2__field1', 'model2_field2', ...]
        duplicate_headings_check = []
        # cycle through all heading columns
        for i, heading in enumerate(headings_row):
            # remove from first heading the byte order mark (BOM) character that may have been placed into the CSV
            if i == 0:
                bom_utf8 = BOM_UTF8.decode(self.csv_encoding)
                if heading.startswith(bom_utf8):
                    heading = heading[len(bom_utf8):]
            model_name, field_name = self.__parse_template_heading(heading=heading)
            heading_for_duplicate_check = f'{model_name}.{field_name}'
            # heading has already been parsed, and so it a duplicate
            if heading_for_duplicate_check in duplicate_headings_check:
                self.__finish_import_and_raise_exception(
                    err=f'Field {field_name} appears more than once for model {model_name}'
                )
            # heading has not yet been parsed
            else:
                duplicate_headings_check.append(heading_for_duplicate_check)
            # check cache, if this model has already been processed
            if model_name not in cached_model_classes:
                # ensure model can be imported
                if model_name not in AbstractConfiguration.models_in_wholesale_allowlist():
                    self.__finish_import_and_raise_exception(
                        err=f'Model {model_name} is not in the allowlist for wholesale import'
                    )
                # check if this model has somehow already been added to the import list
                elif model_name in import_models:
                    self.__finish_import_and_raise_exception(
                        err=f'Model {model_name} appears twice for wholesale import, perhaps due to column ordering'
                    )
                app_name = ModelHelper.get_app_name(model=model_name)
                model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model_name)
            else:
                model_class = cached_model_classes[model_name]
            # check if field can be imported
            if field_name in AbstractConfiguration.fields_in_wholesale_denylist():
                self.__finish_import_and_raise_exception(err=f'Field {field_name} is in denylist for wholesale import')
            # metadata for particular field
            field_type, rel_model_class = self.__get_field_metadata(
                field_name=field_name,
                model_name=model_name,
                model_class=model_class,
            )
            # metadata for particular field
            rel_model_name = None if rel_model_class is None \
                else ModelHelper.get_str_for_cls(model_class=rel_model_class)
            # metadata that corresponds to list CSV column indices
            self.__add_to_metadata_by_col_index(
                model_name=model_name,
                field_name=field_name,
                field_type=field_type,
                rel_model_name=rel_model_name
            )
            # field is a relation that references a model
            if rel_model_class is not None:
                # metadata that can be accessed using strings representing relation model names
                self.__add_to_metadata_by_rel_model_name(rel_model_name=rel_model_name, rel_model_class=rel_model_class)
            # field is a many-to-many relation
            if field_type == self.__m2m_rel_type:
                # metadata for many-to-many fields
                actual_field_name = field_name if not field_name.endswith(self.external_id_suffix) \
                    else field_name[:-len(self.external_id_suffix)]
                m2m_field = getattr(model_class, actual_field_name)
                self.__add_to_m2m_metadata_by_model_name(
                    model_name=model_name,
                    rel_model_name=rel_model_name,
                    field_name=field_name,
                    through_model_class=m2m_field.through
                )
            model_fields.append(field_name)
            # if this is the last column
            if i+1 >= num_of_cols:
                add_model = True
            # this is not the last column
            else:
                # look ahead to the next heading
                next_model_name, _ = self.__parse_template_heading(heading=headings_row[i+1])
                add_model = next_model_name != model_name
            # if the model is ready to add to the metadata, i.e. this is the last column, or the next model is different
            if add_model:
                # metadata that can be accessed using strings representing model names
                self.__add_to_metadata_by_model_name(
                    model_name=model_name,
                    model_class=model_class,
                    model_fields=tuple(model_fields)
                )
                import_models.append(model_name)
                model_fields = []
        self.import_models = import_models

    def __check_for_pk_cols(self):
        """ Checks that each model defined in the template either:
                (a) has a database primary key or external primary key column defined, if the import is an update; OR
                (b) doesn't have a database primary key or external primary key column defined, if the import is an add.

        :return: Nothing.
        """
        # all models must have "id" or "id__external" if import action is update
        # all models must not have "id" or "id__external" if import action is add
        pk_err = ''
        num_of_cols = len(self._metadata_by_col_index)
        # no columns were found
        if num_of_cols == 0:
            self.__finish_import_and_raise_exception(err='No columns were found in the import template.')
        model_name = self._metadata_by_col_index[0][self.__model_name_index]
        # true when "id" column is found, i.e. direct PK
        found_id_col = False
        # true when "id__external" is found, i.e. indirect PK through external ID
        found_external_id_col = False
        # cycle through the columns and models
        for i in range(0, num_of_cols):
            # if we've not already found both identifier columns
            if not (found_id_col and found_external_id_col):
                field_name = self._metadata_by_col_index[i][self.__field_name_index]
                # check if field is the direct PK identifier column
                if field_name == self._id_col:
                    found_id_col = True
                # check if field is the indirect PK identifier column, i.e. through external ID
                elif field_name == self._id_external_col:
                    found_external_id_col = True
            # check if this is the last column, or if the next column is a new model
            if i+1 >= num_of_cols or self._metadata_by_col_index[i+1][self.__model_name_index] != model_name:
                # direct or indirect PK column was not found and the import is an update action
                if self.is_update and not (found_id_col or found_external_id_col):
                    pk_err += f' Model {model_name} does not have an "{self._id_col}" or "{self._id_external_col}" ' \
                              f'column that is required to update.'
                # direct PK column was found and the import is an add action
                elif found_id_col and self.is_add:
                    pk_err += f' Model {model_name} has an "{self._id_col}" column that is not allowed during adds.'
                # get next model, if it exists
                model_name = '' if i+1 >= num_of_cols else self._metadata_by_col_index[i+1][self.__model_name_index]
                # reset found id columns
                found_id_col = False
                found_external_id_col = False
        # some models were missing identifier columns and the action was an update, OR
        # some models had identifier columns and the action was an add
        if pk_err:
            self.__finish_import_and_raise_exception(err=pk_err)

    def __check_import_metadata(self):
        """ Checks the contents of the data structures storing metadata about the import to ensure that they are valid.

        :return: Nothing.
        """
        # check for required or disallowed identifier columns, depending on whether import is add or update
        self.__check_for_pk_cols()

    def __skip_record_due_to_value(self, model_name, field_name, expected_type, field_val):
        """ Skips importing a particular record because one of the values assigned to a field is invalid.

        Raises SkipWholeSaleImportRecord exception.

        :param model_name: Name of model for record.
        :param field_name: Name of field with invalid value.
        :param expected_type: String representation of the type of value that this field expects.
        :param field_val: Invalid value.
        :return: Nothing.
        """
        raise SkipWholesaleImportRecord(
            f'Field {field_name} for model {model_name} expects {expected_type} values but was assigned: {field_val}'
        )

    def __get_val_as_external_pk(self, cell, skip_rec_dict):
        """ Retrieves a value as an external primary key (excluding relation fields such as FKs, O2Os and M2Ms
        referenced through external IDs), or raises an exception if the value cannot be cast as such.

        :param cell: Cell that contains value to cast.
        :param skip_rec_dict: Dictionary that can be expanded into keyword arguments when raising an exception to skip
        the record.
        :return: Value as an external primary key.
        """
        # external primary keys must be defined
        if cell in self.empty_cell_vals:
            self.__skip_record_due_to_value(field_val=cell, expected_type='external PK', **skip_rec_dict)
        external_pk = str(cell).strip()
        # external primary keys must be defined
        if not external_pk:
            self.__skip_record_due_to_value(field_val=external_pk, expected_type='external PK', **skip_rec_dict)
        return external_pk

    def __get_val_as_boolean(self, typed_val, cell, skip_rec_dict):
        """ Retrieves a value as a boolean, or None if value is undefined, or raises an exception if the value cannot
        be cast as such.

        :param typed_val: Default to which the typed value is initialized.
        :param cell: Cell that contains value to cast.
        :param skip_rec_dict: Dictionary that can be expanded into keyword arguments when raising an exception to skip
        the record.
        :return: Value as a boolean, or None if the value is undefined.
        """
        # value is already a boolean
        if isinstance(cell, bool):
            typed_val = cell
        # not yet a boolean
        else:
            # cell is empty
            if cell in self.empty_cell_vals:
                return None
            str_cell = str(cell).lower()
            # value is true
            if str_cell in self.true_booleans:
                typed_val = True
            # value is false
            elif str_cell in self.false_booleans:
                typed_val = False
            # invalid boolean
            else:
                self.__skip_record_due_to_value(field_val=str_cell, expected_type='boolean', **skip_rec_dict)
        return typed_val

    def __get_val_as_int(self, typed_val, cell, skip_rec_dict):
        """Retrieves a value as an int, or None if value is undefined, or raises an exception if the value cannot be
        cast as such.

        :param typed_val: Default to which the typed value is initialized.
        :param cell: Cell that contains value to cast.
        :param skip_rec_dict: Dictionary that can be expanded into keyword arguments when raising an exception to skip
        the record.
        :return: Value as an int, or None if the value is undefined.
        """
        # value is already an int
        if isinstance(cell, int):
            typed_val = cell
        # not yet an int
        else:
            # cell is empty
            if cell in self.empty_cell_vals:
                return None
            try:
                typed_val = int(cell)
            except ValueError:
                self.__skip_record_due_to_value(field_val=cell, expected_type='int', **skip_rec_dict)
        return typed_val

    def __get_val_as_decimal(self, typed_val, cell, skip_rec_dict):
        """Retrieves a value as a decimal, or None if value is undefined, or raises an exception if the value cannot
        be cast as such.

        :param typed_val: Default to which the typed value is initialized.
        :param cell: Cell that contains value to cast.
        :param skip_rec_dict: Dictionary that can be expanded into keyword arguments when raising an exception to skip
        the record.
        :return: Value as a decimal, or None if the value is undefined.
        """
        # value is already a decimal
        if isinstance(cell, Decimal):
            typed_val = cell
        # not yet a decimal
        else:
            # cell is empty
            if cell in self.empty_cell_vals:
                return None
            try:
                typed_val = Decimal(cell)
            except ValueError:
                self.__skip_record_due_to_value(field_val=cell, expected_type='decimal', **skip_rec_dict)
        return typed_val

    @classmethod
    def __get_val_as_str(cls, cell):
        """Retrieves a value as a str, or blank/empty string if value is undefined.

        :param cell: Cell that contains value to cast.
        :return: Value as a str, or blank/empty string if the value is undefined.
        """
        # value is already a string
        if isinstance(cell, str):
            typed_val = cell
        # not yet a string
        else:
            # cell is empty
            if cell in cls.empty_cell_vals:
                return ''
            typed_val = str(cell)
        # strip superfluous whitespace
        typed_val = typed_val.strip()
        return typed_val

    def __get_val_as_date(self, typed_val, cell, skip_rec_dict):
        """Retrieves a value as a date, or None if value is undefined, or raises an exception if the value cannot be
        cast as such.

        :param typed_val: Default to which the typed value is initialized.
        :param cell: Cell that contains value to cast.
        :param skip_rec_dict: Dictionary that can be expanded into keyword arguments when raising an exception to skip
        the record.
        :return: Value as a date, or None if the value is undefined.
        """
        # value is already a date
        if isinstance(cell, date):
            typed_val = cell
        # not yet a date
        else:
            # cell is empty
            if cell in self.empty_cell_vals:
                return None
            try:
                # Passing a datetime to a date field will successfully create a version through the django-reversion
                # package, but this version cannot then be loaded through the History view in the Admin.
                # The resulting error message will be: "Could not load YYY version - incompatible version data."
                typed_val = datetime.strptime(str(cell).strip(), self.date_format).date()
            except ValueError:
                self.__skip_record_due_to_value(field_val=cell, expected_type='date', **skip_rec_dict)
        return typed_val

    def __get_val_as_datetime(self, typed_val, cell, skip_rec_dict):
        """Retrieves a value as a datetime, or None if value is undefined, or raises an exception if the value cannot
        be cast as such.

        :param typed_val: Default to which the typed value is initialized.
        :param cell: Cell that contains value to cast.
        :param skip_rec_dict: Dictionary that can be expanded into keyword arguments when raising an exception to skip
        the record.
        :return: Value as a datetime, or None if the value is undefined.
        """
        # value is already a datetime
        if isinstance(cell, datetime):
            typed_val = cell
        # not yet a datetime
        else:
            # cell is empty
            if cell in self.empty_cell_vals:
                return None
            try:
                typed_val = datetime.strptime(str(cell).strip(), self.datetime_format)
            except ValueError:
                self.__skip_record_due_to_value(field_val=cell, expected_type='datetime', **skip_rec_dict)
        return typed_val

    def __get_val_as_json(self, typed_val, cell, skip_rec_dict):
        """Retrieves a value as JSON, or None if value is undefined, or raises an exception if the value cannot
        be cast as such.

        :param typed_val: Default to which the typed value is initialized.
        :param cell: Cell that contains value to cast.
        :param skip_rec_dict: Dictionary that can be expanded into keyword arguments when raising an exception to skip
        the record.
        :return: Value as JSON, or None if the value is undefined.
        """
        # cell is empty
        if cell in self.empty_cell_vals:
            return None
        # value is a string, so attempt to decode
        if isinstance(cell, str):
            # decoding JSON with double quotes, i.e. {"key": value}
            try:
                typed_val = json_loads(cell)
            except JSONDecodeError:
                # decoding JSON with single quotes, i.e. {'key': value}
                try:
                    # see: https://docs.python.org/3/library/ast.html#ast.literal_eval
                    typed_val = literal_eval(cell)
                except ValueError:
                    self.__skip_record_due_to_value(field_val=cell, expected_type='json', **skip_rec_dict)
        # value is not a string, so attempt to encode it
        else:
            try:
                json_dumps(cell)
                typed_val = cell
            except TypeError:
                self.__skip_record_due_to_value(field_val=cell, expected_type='json', **skip_rec_dict)
        return typed_val

    def __prepare_a_relation_for_import(
            self, is_m2m, row_num, column_index, model_name, field_name, cell, attr_dict, instance_m2ms
    ):
        """ Prepares for import a single relation field such as a foreign key, one-to-one field or many-to-many field.

        For empty cells:
            For many-to-many fields, do nothing.

            For other fields, sets the field value to None.

        For non-empty cells:

            Uses _by_name_non_m2m_rel_data_by_model_name and _by_external_id_non_m2m_rel_data_by_model_name data
            structures for foreign keys and one-to-one fields.

            Uses _by_name_m2m_rel_data_by_model_name and _by_external_id_m2m_rel_data_by_model_name data structures
            for many-to-many fields.

            These data structures will be evaluated and/or imported before the main model instances are imported, and
            during this process the evaluated and/or imported references will be linked back to the main model instances
            such as through the _data_by_model_name data structure.

        :param is_m2m: True if relation is a defined through a many-to-many field, false otherwise.
        :param row_num: Row number in the CSV template to which this relation corresponds, starting at 0.
        :param column_index: Column index in the CSV template to which this relation corresponds, starting at 0.
        :param model_name: Name of main model on which field is relation field is declared.
        :param field_name: Name of relation field on main model.
        :param cell: Cell value from CSV template that defines the relation field's value.
        :param attr_dict: A dictionary of attributes and their values as key/value pairs that define the main model
        instance that is currently being prepared.
        :param instance_m2ms: List of many-to-many field/values tuples. Will be ignored if is_m2m is False.
        Use __get_data_for_m2m_in_data_by_model_name(...) to generate tuples.
        :return: Nothing.
        """
        # cell is empty
        if cell in self.empty_cell_vals:
            # this is a relation through a many-to-many field
            if is_m2m:
                # many-to-many relations will be automatically cleared during "update" imports
                # see clear_first parameter in __add_many_to_many_to_database(...)
                pass
            # this is a relation that is not through a many-to-many field
            else:
                actual_field_name = \
                    field_name[:-len(self.external_id_suffix)] if field_name.endswith(self.external_id_suffix) \
                    else field_name
                attr_dict[actual_field_name] = None
            return
        # for many-to-many relations the cell may contains several values separated by commas, for all other relations
        # it contains a single value
        actual_cell_vals = [cell] if not is_m2m else str(cell).split(self.m2m_delimiter)
        # model referenced by the relation
        rel_model_name = self._metadata_by_col_index[column_index][self.__rel_model_name_index]
        # external ID / IDs
        if field_name.endswith(self.external_id_suffix):
            actual_field_name = field_name[:-len(self.external_id_suffix)]
            # cycle through actual cell values
            for actual_cell_val in actual_cell_vals:
                external_id = str(actual_cell_val).strip()
                # add to data structure storing records referenced through external IDs
                self.__add_to_by_external_id_rel_data_by_model_name(
                    is_m2m=is_m2m,
                    model_name=model_name,
                    rel_model_name=rel_model_name,
                    external_id=external_id,
                    row_num=row_num,
                    actual_field_name=actual_field_name
                )
        # internal ID / IDs, or get-by-name / get-by-names
        else:
            id_suffix = '_id'
            # list of primary keys referencing many-to-many relations, only used when is_m2m=True
            pks = []
            # cycle through actual cell values
            for actual_cell_val in actual_cell_vals:
                pk = None
                is_pk = True
                # attempt to convert value into a database primary key
                try:
                    pk = int(str(actual_cell_val).strip())
                except ValueError:
                    is_pk = False
                # this is an internal database primary key
                if is_pk:
                    # field is many-to-many
                    if is_m2m:
                        pks.append(pk)
                    # field is one-to-one or foreign key
                    else:
                        # convert field to ID reference, e.g. "type" becomes "type_id"
                        fk_field_name = field_name if field_name.endswith(id_suffix) else f'{field_name}{id_suffix}'
                        attr_dict[fk_field_name] = pk
                # this is a by-name reference to another model instance
                else:
                    actual_field_name = field_name if not field_name.endswith(id_suffix) \
                        else field_name[:-len(id_suffix)]
                    named_instance = str(actual_cell_val).strip()
                    # add to data structure storing records referenced through name values
                    self.__add_to_by_name_rel_data_by_model_name(
                        is_m2m=is_m2m,
                        model_name=model_name,
                        rel_model_name=rel_model_name,
                        named_instance=named_instance,
                        row_num=row_num,
                        actual_field_name=actual_field_name
                    )
            # if processing a many-to-many field and a list of PKs have been created, then append the corresponding
            # tuple that will later be added to the _data_by_model_name data structure
            if is_m2m and pks:
                m2m_tuple = self.__get_data_for_m2m_in_data_by_model_name(field_name=field_name, field_values=pks)
                instance_m2ms.append(m2m_tuple)

    def __prepare_data_for_import(self, reader):
        """ Prepares for import all data found in CSV template.

        Uses _data_by_model_name data structure to store definitions for model instances to create or update, or the
        lists of errors that were encountered while attempting to define model instances.

        :param reader: Instantiated reader object from the csv module that allows for iterating over the CSV file.
        :return: Nothing.
        """
        # only prepare import, if there are models to import
        if self.import_models:
            imported_rows = 0
            errors_rows = 0
            # cycle through all rows of data
            for data_row_num, data_row in enumerate(reader):
                attr_dict = {}
                skip_record = False
                err_msgs = []
                num_of_cols = len(data_row)
                external_pk = None
                instance_m2ms = []
                # cycle through all fields for row (may include multiple models, and so multiple records)
                for i, cell in enumerate(data_row):
                    metadata_for_col = self._metadata_by_col_index[i]
                    model_name = metadata_for_col[self.__model_name_index]
                    field_name = metadata_for_col[self.__field_name_index]
                    field_type = metadata_for_col[self.__field_type_index]
                    # if not skipping the record
                    if not skip_record:
                        # ignore blank cells during adds but parse them during updates
                        if (cell not in self.empty_cell_vals and self.is_add) or self.is_update:
                            typed_val = None
                            # unchanging keyword arguments for __skip_record_due_to_value(...)
                            skip_rec_dict = {'model_name': model_name, 'field_name': field_name}
                            # unchanging keyword arguments for __get_val_as_<type>(...)
                            get_val_dict = {'cell': cell, 'typed_val': typed_val, 'skip_rec_dict': skip_rec_dict}
                            try:
                                # field is not on the model, and should be used to create a record that stores the
                                # instance's external ID
                                if field_type == self.__external_pk_type:
                                    external_pk = self.__get_val_as_external_pk(cell=cell, skip_rec_dict=skip_rec_dict)
                                # field expects a boolean
                                elif field_type == self.__bool_type:
                                    typed_val = self.__get_val_as_boolean(**get_val_dict)
                                # field expects an int
                                elif field_type == self.__int_type:
                                    typed_val = self.__get_val_as_int(**get_val_dict)
                                # field excepts a decimal
                                elif field_type == self.__decimal_type:
                                    typed_val = self.__get_val_as_decimal(**get_val_dict)
                                # field excepts a string
                                elif field_type == self.__str_type:
                                    typed_val = self.__get_val_as_str(cell=cell)
                                # field expects a date
                                elif field_type == self.__date_type:
                                    typed_val = self.__get_val_as_date(**get_val_dict)
                                # field expects a datetime
                                elif field_type == self.__datetime_type:
                                    typed_val = self.__get_val_as_datetime(**get_val_dict)
                                # field expects JSON
                                elif field_type == self.__json_type:
                                    typed_val = self.__get_val_as_json(**get_val_dict)
                                # field is a relation that is not many-to-many
                                elif field_type == self.__non_m2m_rel_type:
                                    self.__prepare_a_relation_for_import(
                                        is_m2m=False,
                                        row_num=data_row_num,
                                        column_index=i,
                                        model_name=model_name,
                                        field_name=field_name,
                                        cell=cell,
                                        attr_dict=attr_dict,
                                        instance_m2ms=instance_m2ms
                                    )
                                # field is a relation that is many-to-many
                                elif field_type == self.__m2m_rel_type:
                                    self.__prepare_a_relation_for_import(
                                        is_m2m=True,
                                        row_num=data_row_num,
                                        column_index=i,
                                        model_name=model_name,
                                        field_name=field_name,
                                        cell=cell,
                                        attr_dict=attr_dict,
                                        instance_m2ms=instance_m2ms
                                    )
                                # field is unexpected
                                else:
                                    raise SkipWholesaleImportRecord(
                                        f'Field {field_name} for model {model_name} did not have a known type'
                                    )
                                # only add the field/value combination to the attribute dictionary defining the model
                                # instance, if the value is defined
                                if typed_val is not None:
                                    attr_dict[field_name] = typed_val
                            # some exception occurred
                            except SkipWholesaleImportRecord as err:
                                skip_record = True
                                err_msgs.append(str(err))
                    # check if this is the last column in row, or if the next column is a new model
                    if i + 1 >= num_of_cols or self._metadata_by_col_index[i+1][self.__model_name_index] != model_name:
                        # skipping this record because of an error
                        if skip_record:
                            # add list of error messages in the spot where the model instance would be
                            self.__add_to_data_by_model_name(
                                model_name=model_name,
                                instance_attr_dic=None,
                                instance_external_id=None,
                                instance_m2ms=[],
                                errors=err_msgs
                            )
                            errors_rows += 1
                        # saving this record
                        else:
                            # add model instance to list of all instances
                            self.__add_to_data_by_model_name(
                                model_name=model_name,
                                instance_attr_dic=attr_dict,
                                instance_external_id=external_pk,
                                instance_m2ms=instance_m2ms,
                                errors=None
                            )
                            imported_rows += 1
                        # reset model instance specific variables such as attributes, error messages and whether to skip
                        attr_dict = {}
                        err_msgs = []
                        skip_record = False
                        external_pk = None
                        instance_m2ms = []
            # update metadata
            self.imported_rows = imported_rows
            self.error_rows = errors_rows

    def __before_import(self):
        """ Before the actual import of data, creates and populates data structures for metadata used during the import,
        performs validation checks on that metadata, and then creates and populates data structures holding the data
        that is ready for import.

        :return: Nothing.
        """
        decoded_string_content = self.__get_decoded_string_content()
        with StringIO(decoded_string_content) as string_io:
            reader = self.__get_csv_reader(string_io=string_io)
            # creates and populates data structures to store metadata used during the import such as models involved,
            # their fields, and those fields' types
            self.__make_import_metadata(reader=reader)
            # checks data structures storing metadata used during import
            self.__check_import_metadata()
            # prepare data for import
            self.__prepare_data_for_import(reader=reader)

    def __add_m2m_val_to_data_by_model_name(self, model_name, row_num, field_name, instance_pk):
        """ Adds a single value intended for a many-to-many field to the _data_by_model_name data structure.

        :param model_name: Name of model that declares the many-to-many field.
        :param row_num: Row number for model instance in the CSV template, starting at 0.
        :param field_name: Name of field defining many-to-many relation.
        :param instance_pk: Primary key to model instance referenced through many-to-many field.
        :return: Nothing.
        """
        # set if the many-to-many field has already been added for this model instance
        m2m_tuple_index = None
        m2m_tuples = self._data_by_model_name[model_name][row_num][self.__instance_m2m_index]
        for i, m2m_tuple in enumerate(m2m_tuples):
            # found many-to-many field
            if field_name == m2m_tuple[self.__m2m_field_name_index]:
                m2m_tuple_index = i
                break
        # this many-to-many field has not yet been added for this model instance
        if m2m_tuple_index is None:
            (self._data_by_model_name[model_name][row_num][self.__instance_m2m_index]).append(
                self.__get_data_for_m2m_in_data_by_model_name(
                    field_name=field_name,
                    field_values=[instance_pk]
                )
            )
        # this many-to-many field has already been added for this model instance
        else:
            (
                self._data_by_model_name[model_name][row_num][self.__instance_m2m_index][m2m_tuple_index][
                    self.__m2m_field_values_index
                ]
            ).append(instance_pk)

    def __add_fk_val_to_data_by_model_name(self, model_name, row_num, field_name, instance_pk):
        """ Adds a single value intended for a one-to-one field or foreign key to the _data_by_model_name data
        structure.

        :param model_name: Name of model that declares the one-to-one field or foreign key.
        :param row_num: Row number for model instance in the CSV template, starting at 0.
        :param field_name: Name of field defining relation.
        :param instance_pk: Primary key to model instance referenced through relation.
        :return: Nothing.
        """
        fk = f'{field_name}_id'
        self._data_by_model_name[model_name][row_num][self.__instance_attr_dict_index][fk] = instance_pk

    def __add_rel_val_to_data_by_model_name(self, dict_by_model_name, err_msg, is_m2m, instance_pk):
        """ Adds a relation value intended for a one-to-one field, foreign key or many-to-many field to
        the _data_by_model_name_ data structure.

        :param dict_by_model_name: Relevant data structure in the form of a dictionary where keys are model names.
        :param err_msg: Error message if an error was encountered while evaluating/importing relation. Will be None if
        no error was encountered.
        :param is_m2m: True if relation is for a many-to-many field, false otherwise.
        :param instance_pk: Primary key for instance referenced by relation.
        :return: Nothing.
        """
        # cycle through main models that reference this relation model
        for model_name in dict_by_model_name.keys():
            model_list = dict_by_model_name[model_name]
            # cycle through tuples representing instances that reference the relation model instance
            # by name OR by external ID
            for instance_tuple in model_list:
                row_num = instance_tuple[self.__data_row_index]
                field_name = instance_tuple[self.__actual_field_name_index]
                error_encountered = err_msg is not None
                # a placeholder list of error messages was found for this referencing model instance
                if isinstance(self._data_by_model_name[model_name][row_num], list):
                    # an error was encountered attempting to create instance with the desired name OR to retrieve
                    # instance with desired external ID
                    if error_encountered:
                        self._data_by_model_name[model_name][row_num].append(err_msg)
                # the referencing model instance was found
                elif isinstance(self._data_by_model_name[model_name][row_num], tuple):
                    # change model instance to error that was encountered attempting to create instance
                    # with the desired name OR retrieve instance with desired external ID
                    if error_encountered:
                        self._data_by_model_name[model_name][row_num] = [err_msg]
                        self.imported_rows -= 1
                        self.error_rows += 1
                    # add reference in model instance to newly created instance with the desired name OR newly
                    # retrieved instance with desired external ID
                    else:
                        # dictionary that can be expanded into keyword arguments for add method calls
                        add_kwargs = {
                            'model_name': model_name,
                            'row_num': row_num,
                            'field_name': field_name,
                            'instance_pk': instance_pk
                        }
                        # this relation was referenced through a many-to-many field
                        if is_m2m:
                            self.__add_m2m_val_to_data_by_model_name(**add_kwargs)
                        # this relation was referenced through one-to-one field or foreign key
                        else:
                            self.__add_fk_val_to_data_by_model_name(**add_kwargs)
                # unexpected type
                else:
                    raise StopWholesaleImportException(
                        f'The _data_by_model_name data structure is corrupted at '
                        f'["{model_name}"][{row_num}], and contains: '
                        f'{self._data_by_model_name[model_name][row_num]}.'
                    )

    def __import_relation_models_by_name(self, import_these_models):
        """ Imports (i.e. creates or retrieves) the model instances that are referenced by name through relation fields
        such as foreign keys, one-to-one fields and many-to-many fields.

        Unless specified through the import_specific_models argument, this will skip import of any main models that
        appeared in the CSV template file, even if they are referenced through relations.

        Once relation models are created or retrieved if they already existed, this will link in those relation model
        instances through _data_by_model_name data structure.

        :param import_these_models: Iterable of models that should be imported regardless of whether they appear in the
        CSV template file or not.
        :return: Nothing.
        """
        fields = ['pk', 'name']
        data_struct_tuples = [
            (
                '_by_name_non_m2m_rel_data_by_model_name',  # name of property storing data structure
                False  # False if not for many-to-many fields
            ),
            (
                '_by_name_m2m_rel_data_by_model_name',  # name of property storing data structure
                True  # True if for many-to-many fields
            )
        ]
        # cycle through data structures
        for data_struct_tuple in data_struct_tuples:
            data_struct_name = data_struct_tuple[0]
            is_m2m = data_struct_tuple[1]
            data_struct = getattr(self, data_struct_name)
            imported_rel_model_names = []
            # cycle through models that are referenced through relation fields
            for rel_model_name in data_struct.keys():
                # only import relation model if not a main model or was specifically requested to be imported
                if rel_model_name in import_these_models or rel_model_name not in self.import_models:
                    imported_rel_model_names.append(rel_model_name)
                    rel_model_dict = data_struct[rel_model_name]
                    rel_model_class = self._metadata_by_rel_model_name[rel_model_name]
                    # all values referenced "by name"
                    rel_names = rel_model_dict.keys()
                    #: TODO: Multiple references below to "name" field. Not all relation models may have this field.
                    # in the format of: [Q(...), Q(...), ...]
                    list_of_q = map(lambda name_val: Q(name__iexact=name_val), rel_names)
                    # in the format of: Q(...) | Q(...) | ...
                    by_names_filter = reduce(lambda q1, q2: q1 | q2, list_of_q)
                    by_name_instances = [
                        # tuple is in the format of:
                        #     [0] lower_case_name (i.e. case-insensitive for comparison)
                        #     [1] PK
                        #     [2] name (i.e. original case-sensitivity preserved)
                        (str(r[1]).lower(), r[0], r[1])
                        for r in rel_model_class.objects.only(*fields).filter(by_names_filter).values_list(*fields)
                    ]
                    # List of tuples, in the format of: [(instance_1, rel_name_1), (instance_2, rel_name_2), ....]
                    instance_tuples_to_add = []
                    # cycle through name values that represent instances in this relation model
                    for rel_name in rel_model_dict.keys():
                        rel_name_lower = rel_name.lower()
                        rel_name_dict = rel_model_dict[rel_name]
                        instance_index = None
                        # try and find existing instance by name
                        for i, by_name_instance in enumerate(by_name_instances):
                            # case-insensitive match
                            if rel_name_lower == by_name_instance[0]:
                                instance_index = i
                                break
                        # no instance of relation model matched the name referenced
                        if instance_index is None:
                            # plan to add instance to database later, with bulk_create(...)
                            instance_tuples_to_add.append((rel_model_class(name=rel_name), rel_name))
                        # first instance that matched name with case-insensitive comparison
                        else:
                            instance_pk = by_name_instances[instance_index][1]
                            # add/link relation that was referenced in data to be imported
                            self.__add_rel_val_to_data_by_model_name(
                                dict_by_model_name=rel_name_dict,
                                err_msg=None,
                                is_m2m=is_m2m,
                                instance_pk=instance_pk
                            )
                    # add the "name" references that did not already exist in the database
                    added_instances = rel_model_class.objects.bulk_create([i[0] for i in instance_tuples_to_add])
                    a = len(instance_tuples_to_add)
                    b = len(added_instances)
                    # some "name" references could not be added
                    if a != b:
                        names_to_add = [i[0].name for i in instance_tuples_to_add]
                        added_names = [i.name for i in added_instances]
                        missing_names = [name for name in names_to_add if name not in added_names]
                        missing_names_str = AbstractStringValidator.join_list_of_strings(list_of_strings=missing_names)
                        raise StopWholesaleImportException(f'Could not import the following {rel_model_name} '
                                                           f'relations referenced by name: {missing_names_str}')
                    # create reversion history
                    self.__add_versions_to_database(model_class=rel_model_class, model_instances=added_instances)
                    # add/link relations that were referenced in data to be imported
                    for instance_tuple_to_add, added_instance in zip(instance_tuples_to_add, added_instances):
                        rel_name = instance_tuple_to_add[1]
                        self.__add_rel_val_to_data_by_model_name(
                            dict_by_model_name=rel_model_dict[rel_name],
                            err_msg=None,
                            is_m2m=is_m2m,
                            instance_pk=added_instance.pk
                        )
            # remove the imported relation model from the data structure
            for imported_rel_model_name in imported_rel_model_names:
                del data_struct[imported_rel_model_name]

    def __import_relation_models_by_external_id(self, import_these_models):
        """ Retrieves the model instances that are referenced by external ID through relation fields such as foreign
        keys, one-to-one fields and many-to-many fields.

        Unless specified through the import_specific_models argument, this will skip import of any main models that
        appeared in the CSV template file, even if they are referenced through relations.

        Once relation models are retrieved, this will link in those relation model instances through
        _data_by_model_name data structure.

        :param import_these_models: Iterable of models that should be imported regardless of whether they appear in the
        CSV template file or not.
        :return: Nothing.
        """
        data_struct_tuples = [
            (
                '_by_external_id_non_m2m_rel_data_by_model_name',  # name of property storing data structure
                False  # False if not for many-to-many fields
            ),
            (
                '_by_external_id_m2m_rel_data_by_model_name',  # name of property storing data structure
                True  # True if for many-to-many fields
            )
        ]
        # cycle through data structures
        for data_struct_tuple in data_struct_tuples:
            data_struct_name = data_struct_tuple[0]
            is_m2m = data_struct_tuple[1]
            data_struct = getattr(self, data_struct_name)
            imported_rel_model_names = []
            # relevant fields in the bulk import table
            bulk_fields = ['table_imported_to', 'pk_imported_to', 'pk_imported_from']
            # cycle through models that are referenced through relation fields
            for rel_model_name in data_struct.keys():
                # only import relation model if not a main model or was specifically requested to be imported
                if rel_model_name in import_these_models or rel_model_name not in self.import_models:
                    imported_rel_model_names.append(rel_model_name)
                    rel_model_dict = data_struct[rel_model_name]
                    external_ids = [external_id for external_id in rel_model_dict.keys()]
                    filter_dict = {'table_imported_to': rel_model_name, 'pk_imported_from__in': external_ids}
                    bulk_list = list(BulkImport.objects.only(*bulk_fields).filter(**filter_dict).values(*bulk_fields))
                    # cycle through external IDs that represent instances in this relation model
                    for external_id in external_ids:
                        err_msg = None
                        instance_pk = None
                        # find external ID in list that was retrieved from the database
                        matching_bulk_list = [b for b in bulk_list if b['pk_imported_from'] == external_id]
                        num_matching = len(matching_bulk_list)
                        # no matching external ID
                        if num_matching < 1:
                            err_msg = f'No record was found in the bulk import table ' \
                                      f'for model {rel_model_name} with external ID {external_id}'
                        # multiple matching external IDs
                        elif num_matching > 1:
                            err_msg = f'More than one record was found in the bulk import table ' \
                                      f'for model {rel_model_name} with external ID {external_id}'
                        # exactly one matching external ID
                        else:
                            instance_pk = matching_bulk_list[0]['pk_imported_to']
                        external_id_dict = rel_model_dict[external_id]
                        # add/link relation that was referenced in data to be imported
                        self.__add_rel_val_to_data_by_model_name(
                            dict_by_model_name=external_id_dict,
                            err_msg=err_msg,
                            is_m2m=is_m2m,
                            instance_pk=instance_pk
                        )
            # remove the imported relation model from the data structure
            for imported_rel_model_name in imported_rel_model_names:
                del data_struct[imported_rel_model_name]

    def __add_many_to_many_to_database(self, model_name, m2ms_to_add, for_instances, clear_first):
        """ Adds the many-to-many field "through" model instances to the database.

        :param model_name: Name of model declaring many-to-many field.
        :param m2ms_to_add: List of lists of tuples representing many-to-many fields and their corresponding values
        lists, to add to the database, in the format of: [...[(m2m_field_name_X, m2m_field_values_X),  ...], ...].
        :param for_instances: List of instances that were created or update, for which the many-to-many field "through"
        model instances should be added.
        :param clear_first: True if each instance's many-to-many field should be cleared of all values prior to adding
        new values, false otherwise.
        :return: Nothing.
        """
        # only add many-to-many field "through" model instances to the database, if any exist
        if model_name in self._m2m_metadata_by_model_name:
            # specific model reference to relevant part of metadata dictionary
            m2m_metadata = self._m2m_metadata_by_model_name[model_name]
            # list of primary keys for the model instances for which to clear many-to-many field values before adding
            # new values
            clear_for_pks = [] if not clear_first else [i.pk for i in for_instances]
            # maps fields names to "through" model instances to add
            m2m_instance_cache = {}
            # maps field names to "through" model classes
            m2m_field_cache = {}
            # cycle through all many-to-many tuples list for each model instance
            for m2m_list, for_instance in zip(m2ms_to_add, for_instances):
                # cycle through all field/values combinations
                for m2m_tuple in m2m_list:
                    m2m_field_name = m2m_tuple[self.__m2m_field_name_index]
                    m2m_field_values = m2m_tuple[self.__m2m_field_values_index]
                    # field has not yet been processed for model instances mapping
                    if m2m_field_name not in m2m_instance_cache:
                        m2m_instance_cache[m2m_field_name] = []
                    # specific field reference to relevant part of metadata dictionary
                    # for example: m2m_field_name='traits' and m2m_metadata['traits__external']
                    if m2m_field_name not in m2m_metadata and not m2m_field_name.endswith(self.external_id_suffix):
                        m2m_field_metadata = m2m_metadata[f'{m2m_field_name}{self.external_id_suffix}']
                    # for example: m2m_field_name='traits' and m2m_metadata['traits']
                    else:
                        m2m_field_metadata = m2m_metadata[m2m_field_name]
                    # name of field referencing model where many-to-many field was declared
                    through_pk_field = m2m_field_metadata[self.__through_pk_index]
                    # name of field referencing model to which many-to-many field "points"
                    through_fk_field = m2m_field_metadata[self.__through_fk_index]
                    # class defining "through" model for many-to-many field
                    through_model_class = m2m_field_metadata[self.__through_model_class_index]
                    # field has not yet been processed for "through" model mapping or "through" reference field mapping
                    if m2m_field_name not in m2m_field_cache:
                        m2m_field_cache[m2m_field_name] = through_model_class
                    # cycle through all values for this many-to-many field for this model instance that should be added
                    for m2m_field_value in m2m_field_values:
                        (m2m_instance_cache[m2m_field_name]).append(
                            through_model_class(
                                **{through_pk_field: for_instance.pk, through_fk_field: m2m_field_value}
                            )
                        )
            # if there exist model instances for which to clear many-to-many fields before adding new values
            if clear_for_pks:
                # cycle through all many-to-many fields for model without taking into account their values
                # redundant so that models with only instances that have no many-to-many values defined, can still have
                # their fields cleared, i.e. those models will not appear in m2m_instance_cache
                for field_name_to_clear in m2m_metadata:
                    field_to_clear_metadata = m2m_metadata[field_name_to_clear]
                    # name of field referencing model where many-to-many field was declared
                    through_pk_field_to_clear = field_to_clear_metadata[self.__through_pk_index]
                    # class defining "through" model for many-to-many field
                    through_model_class = field_to_clear_metadata[self.__through_model_class_index]
                    through_model_class.objects.filter(**{f'{through_pk_field_to_clear}__in': clear_for_pks}).delete()
            # cycle through fully processed many-to-many fields and add their respective values to the database
            for m2m_field_name in m2m_instance_cache:
                through_model_class = m2m_field_cache[m2m_field_name]
                through_model_instances = m2m_instance_cache[m2m_field_name]
                through_model_class.objects.bulk_create(through_model_instances)

    @staticmethod
    def __get_existing_external_ids(model_name, external_ids_to_add):
        """ Retrieves the relevant external IDs that are already recorded for this model in the bulk import table.

        :param model_name: String representation of model name.
        :param external_ids_to_add: List of tuples representing the external IDs that are intended to be added to the
        database. Use the first tuple item for the external ID value, i.e. external_id_tuple[0].
        :return: A tuple:
                    [0] A dictionary mapping existing external IDs to internal database primary keys; and
                    [1] A list of existing external ID values.
        """
        # all of the external IDs to add
        all_external_ids = [
            external_id_tuple[0] for external_id_tuple in external_ids_to_add if external_id_tuple[0] is not None
        ]
        # map between external IDs and internal database primary keys
        fields = ['pk_imported_from', 'pk_imported_to']
        external_to_internal_map = {
            str(tuple_value[0]): int(tuple_value[1]) for tuple_value in BulkImport.objects.filter(
                table_imported_to=model_name,
                pk_imported_from__in=all_external_ids
            ).only(*fields).values_list(*fields)
        }
        # external IDs that already exist
        existing_external_ids = [e for e in external_to_internal_map.keys()]
        return external_to_internal_map, existing_external_ids

    @staticmethod
    def __check_for_duplicate_external_ids(external_ids_to_add):
        """ Checks for duplicate external IDs that may have been defined through the CSV template and
        raises an exception if any are found.

        :param external_ids_to_add: List of tuples representing the external IDs that are intended to be added to the
        database. Use the first tuple item for the external ID value, i.e. external_id_tuple[0].
        :return: Nothing.
        """
        # all external IDs for particular model that were defined in the CSV template, excludes "undefined" IDs,
        # i.e. empty values
        all_defined_external_ids = \
            [external_id_tuple[0] for external_id_tuple in external_ids_to_add if external_id_tuple[0] is not None]
        # deduplicated list of external IDs, in a different order than above
        deduplicated_external_ids = list(set(all_defined_external_ids))
        # some external IDs appeared multiple times
        if len(all_defined_external_ids) != len(deduplicated_external_ids):
            count_dict = defaultdict(int)
            # count number of occurrences for each external ID
            for external_id in all_defined_external_ids:
                count_dict[external_id] += 1
            # only external IDs that appear more than once
            duplicates = ''.join([f'{count_dict[external_id]} X for {external_id}'
                                  for external_id in count_dict if count_dict[external_id] > 1])
            raise StopWholesaleImportException(f'The following external IDs appear more than once: {duplicates}.')

    def __add_revision_to_database(self):
        """ Adds a revision record to the database that is used to group records for the django-reversion package.

        Sets the self._revision property to the revision record that was added to the database.

        :return: Nothing.
        """
        action_txt = self.get_action_display()
        comment = f'Changed through an "{action_txt}" wholesale import with UUID: {self.uuid}'
        # Contains metadata about a revision, and groups together all reversion.models.Version instances created in
        # that revision. See: https://django-reversion.readthedocs.io/en/stable/api.html#reversion-models-revision
        revision = (getattr(Revision, 'objects')).create(
            date_created=now(),
            user=FdpUser.objects.get(email=self.user),
            comment=comment
        )
        self._revision = revision

    def __add_versions_to_database(self, model_class, model_instances):
        """ Adds version records to the database for model instances that have already been saved in the database.

        Based on _add_to_revision(...) in reversion.revisions.py for the django-reversion package.

        Ensure that __add_revision_to_database(...) is called first, as it groups the version records.

        :param model_class: Class for instances for which to add version records.
        :param model_instances: List of model instances for which to add version records. Must be for a single model.
        :return: Nothing.
        """
        model_name = ModelHelper.get_str_for_cls(model_class=model_class)
        a = len(model_instances)
        model_db = router.db_for_write(model_class)
        using = 'default'
        version_options = _get_options(model_class)
        content_type = _get_content_type(model_class, using)
        versions_to_add = [
            # Represents a single model instance serialized in a revision.
            # See: https://django-reversion.readthedocs.io/en/stable/api.html#reversion-models-version
            Version(
                revision=self._revision,
                content_type=content_type,
                object_id=force_str(obj.pk),
                db=model_db,
                format=version_options.format,
                serialized_data=serializers.serialize(
                    version_options.format,
                    (obj,),
                    fields=version_options.fields,
                    use_natural_foreign_keys=version_options.use_natural_foreign_keys,
                ),
                object_repr=force_str(obj),
            ) for obj in model_instances
        ]
        b = len(versions_to_add)
        if a != b:
            raise StopWholesaleImportException(f'Could not add versions to the database for {model_name}. '
                                               f'Length of versions ({b}) must be equal to the length of model '
                                               f'instances ({a}) upon which they are based.')
        added_versions = Version.objects.bulk_create(versions_to_add)
        c = len(added_versions)
        if a != c:
            raise StopWholesaleImportException(f'Could not add versions to the database for all {a} model instances '
                                               f'for {model_name}. Only {c} versions were added.')

    def __add_models_to_database(
            self, model_name, m2ms_to_add, external_ids_to_add, attr_dicts, wholesale_import_records
    ):
        """ Adds model instances to the database, as well as the corresponding external IDs.

        :param model_name: String representation of model class being added to the database.
        :param m2ms_to_add: List of lists of tuples representing many-to-many fields and their corresponding values
        lists, to add to the database, in the format of: [...[(m2m_field_name_X, m2m_field_values_X),  ...], ...].
        :param external_ids_to_add: List of tuples representing external IDs to add to the database, in the
        format of: [(external_id_1, row_num_1), (external_id_2, row_num_2), ...].
        :param attr_dicts: List of dictionaries defining attributes and their values that constitute each model
        instance to add to the database.
        :param wholesale_import_records: List of wholesale import records that will be created for the newly added
        model instances.
        :return: Nothing.
        """
        b = len(external_ids_to_add)
        c = len(attr_dicts)
        d = len(m2ms_to_add)
        if b != c:
            raise StopWholesaleImportException(
                f'Cannot add models in database. Length of attribute dictionaries ({c}) must be equal to length of '
                f'corresponding external ID tuples ({b}).'
            )
        if c != d:
            raise StopWholesaleImportException(
                f'Cannot add models in database. Length of attribute dictionaries ({c}) must be equal to length of '
                f'corresponding many-to-many fields tuples ({d}).'
            )
        # external IDs already recorded in database
        external_to_internal_map, existing_external_ids = self.__get_existing_external_ids(
            model_name=model_name,
            external_ids_to_add=external_ids_to_add
        )
        # some external IDs already exist
        if existing_external_ids:
            ext_ids_str = AbstractStringValidator.join_list_of_strings(list_of_strings=existing_external_ids)
            raise StopWholesaleImportException(f'Cannot add models in database. The following external '
                                               f'IDs already exist: {ext_ids_str}.')
        model_class = self._metadata_by_model_name[model_name][self.__model_class_index]
        # create model instances in database
        instances_to_add = [model_class(**attr_dict) for attr_dict in attr_dicts]
        created_instances = model_class.objects.bulk_create(instances_to_add)
        a = len(created_instances)
        if a != b:
            raise StopWholesaleImportException(
                f'Cannot add models in database. Length of created instances ({a}) must be equal to the length of '
                f'corresponding external ID tuples ({b}). This may be caused because some instances could not be '
                f'created.'
            )
        # create reversion history
        self.__add_versions_to_database(model_class=model_class, model_instances=created_instances)
        # create the corresponding bulk import records in the database
        bulk_instances = [
            BulkImport(
                source_imported_from='wholesale add',
                table_imported_from=model_name,
                pk_imported_from=external_id_tuple[0],
                table_imported_to=model_name,
                pk_imported_to=created_instance.pk,
                data_imported=json_dumps(attr_dict, default=str)
            )
            for created_instance, external_id_tuple, attr_dict in zip(
                created_instances,
                external_ids_to_add,
                attr_dicts
            ) if external_id_tuple[0] is not None
        ]
        BulkImport.objects.bulk_create(bulk_instances)
        # add many-to-many relations for created model instances
        self.__add_many_to_many_to_database(
            model_name=model_name,
            m2ms_to_add=m2ms_to_add,
            for_instances=created_instances,
            clear_first=False
        )
        # add to the list of wholesale import records that will be created later in the database
        for created_instance, external_id_tuple in zip(created_instances, external_ids_to_add):
            wholesale_import_records.append(
                WholesaleImportRecord(
                    wholesale_import=self,
                    row_num=external_id_tuple[1] + 2,
                    model_name=model_name,
                    instance_pk=created_instance.pk,
                    errors=''
                )
            )

    def __update_models_in_database(
            self, model_name, m2ms_to_add, external_ids_to_add, attr_dicts, wholesale_import_records
    ):
        """ Updates model instances in the database, as well as add the corresponding external IDs.

        :param model_name: String representation of model class being updated in the database.
        :param m2ms_to_add: List of lists of tuples representing many-to-many fields and their corresponding values
        lists, to add to the database, in the format of: [...[(m2m_field_name_X, m2m_field_values_X),  ...], ...].
        :param external_ids_to_add: List of tuples representing external IDs to add to the database, in the
        format of: [(external_id_1, row_num_1), (external_id_2, row_num_2), ...].
        :param attr_dicts: List of dictionaries defining attributes and their values that constitute each model
        instance to update in the database.
        :param wholesale_import_records: List of wholesale import records that will be created for the newly updated
        model instances.
        :return: Nothing.
        """
        b = len(external_ids_to_add)
        c = len(attr_dicts)
        d = len(m2ms_to_add)
        if b != c:
            raise StopWholesaleImportException(
                f'Cannot update models in database. Length of attribute dictionaries ({c}) must be equal to length of '
                f'corresponding external ID tuples ({b}).'
            )
        if c != d:
            raise StopWholesaleImportException(
                f'Cannot update models in database. Length of attribute dictionaries ({c}) must be equal to length of '
                f'corresponding many-to-many fields tuples ({d}).'
            )
        # list of fields that reflect the changes
        fields_to_update = self._metadata_by_model_name[model_name][self.__model_fields_index]
        # external IDs already recorded in database
        external_to_internal_map, existing_external_ids = self.__get_existing_external_ids(
            model_name=model_name,
            external_ids_to_add=external_ids_to_add
        )
        # no primary key in fields to update, depend on external ID
        if 'id' not in fields_to_update:
            e = len(existing_external_ids)
            if b != e:
                raise StopWholesaleImportException(
                    f'Cannot update models in database. Length of external ID tuples ({b}) must be equal to length of '
                    f'corresponding existing external IDs ({e}). This may be caused because some external IDs are not '
                    f'recorded in the database, or are recorded multiple times.'
                )
            ids_dict = {
                external_to_internal_map[external_id_tuple[0]]: {
                    # attribute dictionary defining updated values for record
                    'a': attr_dict,
                    # external ID for record
                    'e': external_id_tuple[0],
                    # row number in CSV template for record
                    'r': external_id_tuple[1]
                }
                for external_id_tuple, attr_dict in zip(external_ids_to_add, attr_dicts)
            }
        # primary key in fields to update, so external ID is only for additional/later reference
        else:
            try:
                ids_dict = {
                    # NOTE: assumption is as of Python 3.8, the key is evaluated before the value during dictionary
                    # comprehension, as per https://www.python.org/dev/peps/pep-0572/
                    # otherwise, "id" appears in attribute dictionary that defines updates
                    # primary key for record
                    str(attr_dict.pop('id')): {
                        # attribute dictionary defining updated values for record
                        'a': attr_dict,
                        # external ID for record
                        'e': external_id_tuple[0],
                        # row number in CSV template for record
                        'r': external_id_tuple[1]
                    }
                    for external_id_tuple, attr_dict in zip(external_ids_to_add, attr_dicts)
                }
            except KeyError:
                raise StopWholesaleImportException(
                    f'Cannot update {model_name} model in database. At least one record was missing a primary key.'
                )
        ids_to_update = ids_dict.keys()
        a = len(ids_to_update)
        if a != b:
            #: TODO: Switch to row-by-row import to skip duplicate records.
            raise StopWholesaleImportException(
                f'Cannot update models in database. Length of IDs to update ({a}) must be equal to length of '
                f'corresponding external ID tuples ({b}. This may be caused because the same database record is listed '
                f'multiple times for update.'
            )
        model_class = self._metadata_by_model_name[model_name][self.__model_class_index]
        # retrieve model instances to update from database
        in_bulk_dict = model_class.objects.in_bulk(ids_to_update)
        f = len(in_bulk_dict.keys())
        if a != f:
            #: TODO: Switch to row-by-row import to skip missing records.
            raise StopWholesaleImportException(
                f'Cannot update models in database. Length of instances found in the database ({f}) must be equal to '
                f'length of corresponding IDs to update ({a}). This may be caused because some instances '
                f'specified for update could not be found in the database.'
            )
        # in_bulk(...) may re-order instances, so ensure the order is correct
        ordered_in_bulk_dict = {str_pk: in_bulk_dict[int(str_pk)] for str_pk in ids_to_update}
        # cycle through retrieved primary keys
        for str_pk in ordered_in_bulk_dict:
            # only process this if it was in the original IDs dictionary
            if str_pk in ids_dict:
                id_dict = ids_dict[str_pk]
                # cycle through attributes in attribute dictionary
                for attr in id_dict['a']:
                    # update the attribute with a new value
                    setattr(ordered_in_bulk_dict[str_pk], attr, ids_dict[str_pk]['a'][attr])
        # list of instances to update, with their updated values
        instances_to_update = [ordered_in_bulk_dict[str_pk] for str_pk in ordered_in_bulk_dict]
        # update the corresponding bulk import records in the database, but skip external IDs
        m2m_metadata_for_model = self._m2m_metadata_by_model_name.get(model_name, {})
        m2m_fields = m2m_metadata_for_model.keys()
        # cannot do bulk_update on external fields or many-to-many fields
        bulk_fields = [
            f if not f.endswith(self.external_id_suffix) else f[:-len(self.external_id_suffix)]
            for f in fields_to_update
            if f not in m2m_fields and not f == self._id_external_col and not f == self._id_col
        ]
        # only do bulk update, if there are fields besides external and many-to-many fields
        if bulk_fields:
            model_class.objects.bulk_update(instances_to_update, bulk_fields)
        # create reversion history
        self.__add_versions_to_database(model_class=model_class, model_instances=instances_to_update)
        # create the corresponding bulk import records in the database
        bulk_instances = [
            BulkImport(
                source_imported_from='wholesale update',
                table_imported_from=model_name,
                pk_imported_from=ids_dict[pk]['e'],
                table_imported_to=model_name,
                pk_imported_to=pk,
                data_imported=json_dumps(ids_dict[pk]['a'], default=str)
            )
            # don't create an external ID if one already exists
            for pk in ids_dict if ids_dict[pk]['e'] is not None and ids_dict[pk]['e'] not in existing_external_ids
        ]
        BulkImport.objects.bulk_create(bulk_instances)
        # add many-to-many relations for created model instances
        self.__add_many_to_many_to_database(
            model_name=model_name,
            m2ms_to_add=m2ms_to_add,
            for_instances=instances_to_update,
            clear_first=True
        )
        # add to the list of wholesale import records that will be created later in the database
        for pk in ids_dict:
            wholesale_import_records.append(
                WholesaleImportRecord(
                    wholesale_import=self,
                    row_num=ids_dict[pk]['r'] + 2,
                    model_name=model_name,
                    instance_pk=pk,
                    errors=''
                )
            )

    def __import_main_models(self):
        """ Imports the main models that were defined in the CSV template.

        :return: Nothing.
        """
        wholesale_import_records = []
        if not (self.is_add or self.is_update):
            raise StopWholesaleImportException('Only wholesale import adds and updates are currently supported.')
        # cycle through each main model to import
        for model_name in self.import_models:
            model_instances = self._data_by_model_name.pop(model_name)
            # list of tuples, in the format of: [(external_id_1, row_num_1), (external_id_2, row_num_2), ...]
            external_ids_to_add = []
            # list of lists of tuples, in the format of: [...[(m2m_field_name_X, m2m_field_values_X), ...], ...]
            m2ms_to_add = []
            # list of dictionaries that define instances to create/update
            attr_dicts = []
            # cycle through each model instance to import
            for row_num, instance_tuple in enumerate(model_instances):
                # this model instance cannot be imported
                if isinstance(instance_tuple, list):
                    errors_list = instance_tuple
                    self.__error_wholesale_import_records.append(
                        WholesaleImportRecord(
                            wholesale_import=self,
                            row_num=row_num + 2,
                            model_name=model_name,
                            errors=' '.join(errors_list)
                        )
                    )
                # this model instance can be imported
                elif isinstance(instance_tuple, tuple):
                    attr_dict = instance_tuple[self.__instance_attr_dict_index]
                    external_id = instance_tuple[self.__instance_external_id_index]
                    m2ms_list = instance_tuple[self.__instance_m2m_index]
                    external_ids_to_add.append((external_id, row_num))
                    attr_dicts.append(attr_dict)
                    m2ms_to_add.append(m2ms_list)
                # unexpected type
                else:
                    raise StopWholesaleImportException(
                        f'The _data_by_model_name data structure is corrupted at ["{model_name}"][{row_num}], and '
                        f'contains: {instance_tuple}.'
                    )
            # check for duplicate external IDs
            self.__check_for_duplicate_external_ids(external_ids_to_add=external_ids_to_add)
            # import is an add
            if self.is_add:
                self.__add_models_to_database(
                    model_name=model_name,
                    m2ms_to_add=m2ms_to_add,
                    external_ids_to_add=external_ids_to_add,
                    attr_dicts=attr_dicts,
                    wholesale_import_records=wholesale_import_records
                )
            # import is an update
            elif self.is_update:
                self.__update_models_in_database(
                    model_name=model_name,
                    m2ms_to_add=m2ms_to_add,
                    external_ids_to_add=external_ids_to_add,
                    attr_dicts=attr_dicts,
                    wholesale_import_records=wholesale_import_records
                )
            # update any model instances that may reference the just imported instances by name
            self.__import_relation_models_by_name(import_these_models=(model_name,))
            # update any model instances that may reference the just imported instances by external ID
            self.__import_relation_models_by_external_id(import_these_models=(model_name,))
        # save in the database the model instance that represents the entire import
        self.finish_import_without_raising_exception(err=None)
        self.full_clean()
        self.save()
        # save in the database the model instances that represent each record imported
        WholesaleImportRecord.objects.bulk_create(wholesale_import_records)

    @handle_import_errors
    def do_import(self):
        """ Perform wholesale import.

        :return: Nothing.
        """
        if self.is_ready_for_import:
            # start import
            self.started_timestamp = now()
            # creates and populates metadata for import, perform validation checks and prepares data for import
            self.__before_import()
            # stores wholesale import records that hold errors for rows
            self.__error_wholesale_import_records = []
            try:
                # disable versioning to improve performance
                # If manage_manually=True, versions will not be saved when a model’s save() method is called.
                # This allows version control to be switched off for a given revision block.
                # If atomic=True, the revision block will be wrapped in a transaction.atomic().
                # see: https://django-reversion.readthedocs.io/en/stable/views.html#decorators
                with create_revision(manage_manually=True, atomic=True):
                    # create a revision that will group reversion records for the django-reversion package
                    self.__add_revision_to_database()
                    # create or retrieve model instances that are referenced by name, then update relation fields on
                    # referencing model instances
                    self.__import_relation_models_by_name(import_these_models=())
                    # retrieve model instances that are referenced by external ID, then update relation fields on
                    # referencing model instances
                    self.__import_relation_models_by_external_id(import_these_models=())
                    # import main model instances that were defined in the CSV template
                    self.__import_main_models()
                    # import is now finished, check if there were any issues
                    if self.__error_wholesale_import_records:
                        raise EndedWithErrorsWholesaleImportException
            except (StopWholesaleImportException, EndedWithErrorsWholesaleImportException) as err:
                # did not finish the wholesale import
                # exception was raised during actual import, i.e. adding/updating records in the database
                if isinstance(err, StopWholesaleImportException):
                    self.error_rows = 0
                    self.finish_import_without_raising_exception(err=err)
                # finished the wholesale import
                elif isinstance(err, EndedWithErrorsWholesaleImportException):
                    # some errors were noted per record
                    if self.__error_wholesale_import_records:
                        # save in database the model instances that represent each record to be imported with an error
                        WholesaleImportRecord.objects.bulk_create(self.__error_wholesale_import_records)
                    self.finish_import_without_raising_exception(err=None)
                self.imported_rows = 0
                self.full_clean()
                self.save()

    @staticmethod
    def __add_to_cached_fields_to_add_by_model(
            model_name, field_name, has_pk_vals, rel_model_name, cached_fields_to_add_by_model
    ):
        """ Records a field that should be added for a particular model, and whether it contains primary key values.

        Used during the conversion of implicit references.

        :param model_name: Name of model for which to add field.
        :param field_name: Name of field to add.
        :param has_pk_vals: True if field to add will contain primary key values, false if it will contain external ID
        values.
        :param rel_model_name: Name of model to which field links, if field is a linking field such as a foreign key,
        one-to-one field or many-to-many field; will be None otherwise.
        :param cached_fields_to_add_by_model: Data structure that stores the fields to add in the format of a
        dictionary whose keys are the model names.
        :return: Nothing.
        """
        # no fields have yet needed to be added for this particular model
        if model_name not in cached_fields_to_add_by_model:
            cached_fields_to_add_by_model[model_name] = []
        (cached_fields_to_add_by_model[model_name]).append((field_name, has_pk_vals, rel_model_name))

    def __get_fields_to_convert_implicit_references(self):
        """ Retrieves a data structure that stores the fields to add in the format of a dictionary whose keys are the
        model names.

        Used during the conversion of implicit references.

        Fields may be added that make explicit a link from one model to another model. External ID fields may also be
        added to provide a target (i.e. endpoint) for linking fields.

        :return: Data structure the stores the fields to add.
        """
        # fields to add, in the format of: {
        # 'model_1': [(field_1, is_pk_1, rel_model_1), (field_2, is_pk_2, rel_model_2), ...],
        # 'model_2': [...],
        # ...
        # }
        cached_fields_to_add_by_model = {}
        # no implicit conversion during updates
        if self.is_update:
            return cached_fields_to_add_by_model
        # models that have already been checked, in the format of: {'model_1': (has_id_1, has_external_id_1), ...}
        cached_models_to_the_left = {}
        # cycle through each model
        for import_model in self.import_models:
            model_name_dict = self._metadata_by_model_name[import_model]
            model_name = import_model
            model_class = model_name_dict[self.__model_class_index]
            csv_model_fields = model_name_dict[self.__model_fields_index]
            has_id = self._id_col in csv_model_fields
            has_external_id = self._id_external_col in csv_model_fields
            is_first_model = not cached_models_to_the_left
            cached_models_to_the_left[model_name] = (has_id, has_external_id)
            # only cycle through fields, if this is not the first model
            if not is_first_model:
                db_model_fields = ModelHelper.get_fields(model=model_class)
                # cycle through fields that are noted for model in database
                for field in db_model_fields:
                    field_name = field.name
                    # field is not explicitly defined in csv AND field is a linking field AND
                    if field_name not in csv_model_fields \
                            and ModelHelper.is_field_linked_to_another_model(model=model_class, field=field):
                        # fields links to this model
                        linked_model_name = ModelHelper.get_str_for_cls(model_class=field.remote_field.model)
                        # model that field links to is included in the CSV template
                        if linked_model_name in cached_models_to_the_left:
                            cached_model_tuple = cached_models_to_the_left[linked_model_name]
                            has_pk = cached_model_tuple[0]
                            has_external_id = cached_model_tuple[1]
                            # model to left has a primary key field, so link to this primary key field
                            if has_pk:
                                self.__add_to_cached_fields_to_add_by_model(
                                    model_name=model_name,
                                    field_name=field_name,
                                    has_pk_vals=True,
                                    rel_model_name=linked_model_name,
                                    cached_fields_to_add_by_model=cached_fields_to_add_by_model
                                )
                            # model to left doesn't have a primary key field, so link will be established by external ID
                            else:
                                # don't add field if its external version already exists
                                if f'{field_name}{self.external_id_suffix}' not in csv_model_fields:
                                    self.__add_to_cached_fields_to_add_by_model(
                                        model_name=model_name,
                                        field_name=field_name,
                                        has_pk_vals=False,
                                        rel_model_name=linked_model_name,
                                        cached_fields_to_add_by_model=cached_fields_to_add_by_model
                                    )
                                # model to left doesn't have an external ID field, so it too will be added
                                if not has_external_id:
                                    # link will be established by external ID
                                    self.__add_to_cached_fields_to_add_by_model(
                                        model_name=linked_model_name,
                                        field_name=self._id_external_col,
                                        has_pk_vals=False,
                                        rel_model_name=None,
                                        cached_fields_to_add_by_model=cached_fields_to_add_by_model
                                    )
                                    # update cache for models to the left, with the newly added external ID column
                                    cached_models_to_the_left[linked_model_name] = (has_pk, True)
        return cached_fields_to_add_by_model

    @staticmethod
    def get_auto_external_id(uuid, group, row_num):
        """ Retrieves an external ID that has been automatically generated, such as for the conversion of implicit
        model references to explicit model references.

        :param uuid: UUID for wholesale import.
        :param group: Collection of characters that represents a group of records, such as for a particular table.
        :param row_num: Sequential numbering for external ID.
        :return: External ID that has been automatically generated.
        """
        return f'__AUTO_{uuid}_{group}_{row_num}'

    class FieldToAdd(object):
        """ Each instance of this object stores information about a field that will be added so that implicit references
        between models are converted to explicit references.

        During this conversion process, the CSV template will be regenerated using slices from the original template
        rows.

        """
        def __init__(
                self, is_first, is_last, start, end, last_end, is_field_a_reference,
                orig_col_index, group, reference_group, model_name, field_name
        ):
            """ Creates an instance defining a field that will be added to the CSV template to facilitate making
            an implicit reference between models into an explicit reference.

            :param is_first: True if this is the first field that will be added to the CSV template, false otherwise.
            :param is_last: True if this is the last field that will be added to the CSV template, false otherwise.
            :param start: Starting index for slice from original CSV template. Can be used with a CSV row that is a
            list, i.e. [start:...]. Will be None if there is no relevant slice.
            :param end: Ending index for slice from original CSV template. Can be used with a CSV row that is a
            list, i.e. [...:end]. Will be None if there is no relevant slice.
            :param last_end: Last defined ending index that was used for slice from original CSV template. See 'end'
            argument.
            :param is_field_a_reference: True if the field to add is a reference to another model field, such as when
            adding a foreign key, one-to-one field or many-to-many field. False if the field to add is a primary
            key or external ID.
            :param orig_col_index: Column index in the original CSV template if the field to add is referencing a field
            that existed in the original template. Will be None if the field is referencing a field that was added, or
            if the field is not a reference, i.e. if is_field_a_reference is False.
            :param group: Collection of characters that represents a group of records, such as for a particular table
            on which the field is declared.
            :param reference_group: Collection of characters that represents another group of records, such as for a
            particular table that is referenced by the field. Will be None if is_field_a_reference=False.
            :param model_name: Name of model for which to add field.
            :param field_name: Name of field to add.
            """
            super().__init__()
            self.is_first = is_first
            self.is_last = is_last
            self.start = start if end is not None else None
            self.end = end if start is not None else None
            self.last_end = last_end if last_end is not None else None
            self.is_field_a_reference = is_field_a_reference
            self.orig_col_index = orig_col_index if is_field_a_reference else None
            self.group = group
            self.reference_group = reference_group if is_field_a_reference else None
            self.model_name = model_name
            self.field_name = field_name

        @property
        def has_original_slice(self):
            """ Checks whether any relevant slice of the original CSV template can be taken when adding this field.

            :return: True if a relevant slice of the original CSV template row can be taken, false otherwise.
            """
            return self.start is not None and self.end is not None

        def __get_starting_slice(self, original_csv_row):
            """ Retrieves a slice from the CSV row, if the current field to add is the first of the fields to add, but
            not the first field in the CSV template.

            :param original_csv_row: Original CSV template row.
            :return: Empty list if no relevant slice is retrieved, otherwise a list that represents a slice from the
            original CSV row.
            """
            return [] if not self.is_first else ([] if self.start == 0 else original_csv_row[0: self.start])

        def __get_ending_slice(self, original_csv_row):
            """ Retrieves a slice from the CSV row, if the current field to add is the last of the fields to add, but
            not the last field in the CSV template.

            :param original_csv_row: Original CSV template row.
            :return: Empty list if no relevant slice is retrieved, otherwise a list that represents a slice from the
            original CSV row.
            """
            original_end = len(original_csv_row)
            actual_start = self.end if self.end is not None else (self.last_end if self.last_end is not None else 0)
            return [] if not self.is_last else (
                [] if self.end == original_end else original_csv_row[actual_start: original_end]
            )

        def get_new_heading_slice(self, original_csv_row, field_heading):
            """ Retrieves the slice of a headings row to build a new CSV template, which includes the field, and in some
            cases a slice of a headings row from the original CSV template.

            :param original_csv_row: Original CSV template headings row.
            :param field_heading: Column heading intended for the field to add.
            :return: List of cells that represents a new CSV template headings row.
            """
            new_cell = [field_heading]
            end_cells = self.__get_ending_slice(original_csv_row=original_csv_row)
            # a slice from the original CSV template should be appended to the field
            if self.has_original_slice:
                start_cells = self.__get_starting_slice(original_csv_row=original_csv_row)
                return start_cells + new_cell + original_csv_row[self.start: self.end] + end_cells
            # no slice from the original CSV template is relevant for this field
            else:
                return new_cell + end_cells

        def get_new_data_slice(self, original_csv_row, auto_external_id, reference_auto_external_id):
            """ Retrieves the slice of a data row to build a new CSV template, which includes the field, and in some
            cases a slice of a data row from the original CSV template.

            :param original_csv_row: Original CSV template data row.
            :param auto_external_id: Automatically generated external ID that is only used if field to add is an
            external ID, i.e. if self.is_field_a_reference is False.
            :param reference_auto_external_id: Automatically generated referenced external ID that is only used if field
            to add references a field that did not exist in the original CSV template, i.e. self.is_field_a_reference
            is True and self.orig_col_index is None and self.reference_group is not None.
            :return: List of cells that represents a new CSV template data row.
            """
            # field references another field
            if self.is_field_a_reference:
                # field references a field that existed in the original CSV template
                if self.orig_col_index is not None and self.reference_group is None:
                    new_cell = [original_csv_row[self.orig_col_index]]
                # field references an external ID field that will be added to the new CSV template
                elif self.orig_col_index is None and self.reference_group is not None:
                    new_cell = [reference_auto_external_id]
                # something went wrong
                else:
                    raise StopWholesaleImportException(
                        f'Could not retrieve a new slice while building a new CSV template. Either orig_col_index '
                        f'({self.orig_col_index}) must be None/not None or reference_group ({self.reference_group}) '
                        f'must be None/not None.')
            # field is an external ID
            else:
                new_cell = [auto_external_id]
            end_cells = self.__get_ending_slice(original_csv_row=original_csv_row)
            # a slice from the original CSV template should be appended to the field
            if self.has_original_slice:
                start_cells = self.__get_starting_slice(original_csv_row=original_csv_row)
                return start_cells + new_cell + original_csv_row[self.start: self.end] + end_cells
            # no slice from the original CSV template is relevant for this field
            else:
                return new_cell + end_cells

    def __get_end_col_index_for_model(self, start, model_name):
        """ Retrieves the column index for the original CSV template, for which the fields for the current model end,
        and EITHER fields for a new model begin, OR it is the end of the CSV template columns.

        The column index is based on the original column index before any CSV slices, or any fields that are added.

        See the _metadata_by_col_index data structure.

        :param start: Starting column index for current model.
        :param model_name: Name of current model.
        :return: Column index for where next model begins or the CSV template ends.
        """
        num_of_cols = len(self._metadata_by_col_index)
        # cycle through the columns, starting at the current column
        for i in range(start + 1, num_of_cols):
            referenced_model_name = self._metadata_by_col_index[i][self.__model_name_index]
            # this is a new model
            if model_name != referenced_model_name:
                return i
        # this is the end of the row
        return num_of_cols

    def __get_reference_for_field_to_add(self, is_pk, model_name, fields_to_add):
        """ Retrieves the reference for a field that is to be added when generating a new CSV template from the
        original CSV template to convert implicit model references into explicit references.

        Should only be called if the field to add is a reference field, i.e. if is_field_a_reference is True.

        The field to add may reference a field that existed in the original CSV template such as an external ID or a
        primary key.

        The field to add may also reference another field to be added, which will always be an external ID.

        For parsing the original CSV template, see the _metadata_by_col_index data structure.

        :param is_pk: True if the field to add references the primary key on another model, false if it references the
        external ID.
        :param model_name: Name of model whose primary key or external ID is referenced by field to add.
        :param fields_to_add: List of other fields to add, which may be referenced by this field to add.
        :return: A tuple:
                    [0] Column index in the original CSV template that is referenced by this field, will be None if
                        field references a field that is not yet added; and
                    [1] The group that defines the collection of records referenced by the field, will be None if field
                        referenced a field that existed in the original CSV template.
        """
        # will note the column index where fields start for the model we are looking for
        model_start_index = None
        # name of field being referenced
        field_to_find = self._id_col if is_pk else self._id_external_col
        # cycle through columns in original CSV template, in case field referenced already existed
        for col_index, by_col_tuple in enumerate(self._metadata_by_col_index):
            cur_model_name = by_col_tuple[self.__model_name_index]
            cur_field_name = by_col_tuple[self.__field_name_index]
            # note column index where fields for desired model start
            if model_start_index is None and model_name == cur_model_name:
                model_start_index = col_index
            # found the field for that model
            if model_name == cur_model_name and field_to_find == cur_field_name:
                return col_index, None
        # did not find field for that model in original fields, so check fields to add
        if model_start_index is not None and fields_to_add:
            # cycle through fields to add when building new CSV template
            for i, field_to_add in enumerate(fields_to_add):
                # first field to add for every model will contain the relevant slice from the original CSV template, so
                # compare model indices
                if field_to_add.has_original_slice and field_to_add.start == model_start_index:
                    num_of_fields_to_add = len(fields_to_add)
                    # cycle through fields to add until we've reached a new model
                    for j in range(i, num_of_fields_to_add):
                        cur_field_to_add = fields_to_add[j]
                        # this is a new model, since there is a new relevant slice from the original CSV template
                        if cur_field_to_add.has_original_slice and j > i:
                            break
                        # this is the same model
                        else:
                            # this is an external ID
                            if not cur_field_to_add.is_field_a_reference:
                                return None, cur_field_to_add.group
                    # this is a new model, since there is a new relevant slice from the original CSV template, OR we've
                    # reached the end of the CSV row
                    break
        # did not find field in neither the _metadata_by_col_index data structure nor the fields to add
        raise StopWholesaleImportException(f'Could not find field {field_to_find} for model {model_name} in '
                                           f'the _metadata_by_col_index data structure or in the fields to add.')

    def get_fields_to_add(self, cached_fields_to_add_by_model):
        """ Retrieves a list of fields to add and corresponding slices from the original CSV template, that can be used
        to convert the original CSV template with implicit references into a new CSV template with explicit references.

        :param cached_fields_to_add_by_model: Data structure that stores the fields to add in the format of a
        dictionary whose keys are the model names.
        :return: List of fields to add.
        """
        # list of fields to add and corresponding slices from the original CSV template
        fields_to_add = []
        # models for which the fields to add have already been noted
        done_models = []
        # records the previous ending index used for a slice from the original CSV row, if defined
        last_end = None
        # cycle through fields recorded in metadata, and create fields to add that will be used to rebuild the CSV
        for col_num, by_col_tuple in enumerate(self._metadata_by_col_index):
            # name of model for CSV column
            model_name = by_col_tuple[self.__model_name_index]
            # some fields will be added for this model, and they have not yet been noted
            if model_name in cached_fields_to_add_by_model and model_name not in done_models:
                done_models.append(model_name)
                group = str(len(done_models))
                fields_to_add_tuples = cached_fields_to_add_by_model[model_name]
                #: TODO: Create cache mapping (model, field) -> column_index.
                #: TODO: Create cache of end indexes for each model.
                # cycle through fields to add tuples
                for i, field_to_add_tuple in enumerate(fields_to_add_tuples):
                    field_name = field_to_add_tuple[0]
                    is_pk = field_to_add_tuple[1]
                    rel_model_name = field_to_add_tuple[2]
                    # only include slice from original CSV row once, and so on the first field tuple is enough
                    if i == 0:
                        # starting column for CSV row
                        start = col_num
                        # find where next model starts or CSV row ends
                        end = self.__get_end_col_index_for_model(start=col_num, model_name=model_name)
                    else:
                        start = None
                        end = None
                    # only external ID columns may be added, never internal PK columns
                    is_field_a_reference = field_name != self._id_external_col
                    # if field is a reference to another field, then find the relevant external ID or primary key
                    if is_field_a_reference:
                        orig_col_index, reference_group = self.__get_reference_for_field_to_add(
                            is_pk=is_pk,
                            model_name=rel_model_name,
                            fields_to_add=fields_to_add
                        )
                    else:
                        orig_col_index, reference_group = None, None
                    # don't change the field name if it references a primary key or if it is not a reference at all,
                    # and therefore is an external ID field (and so already have external ID suffix)
                    dont_change_field = is_pk or not is_field_a_reference
                    fields_to_add.append(
                        self.FieldToAdd(
                            is_first=True if not fields_to_add else False,
                            is_last=False,
                            start=start,
                            end=end,
                            last_end=last_end,
                            is_field_a_reference=is_field_a_reference,
                            orig_col_index=orig_col_index,
                            group=group,
                            reference_group=reference_group,
                            model_name=model_name,
                            field_name=field_name if dont_change_field else f'{field_name}{self.external_id_suffix}'
                        )
                    )
                    # current ending index was defined
                    if end is not None:
                        # no previous ending index was recorded
                        if last_end is None:
                            last_end = end
                        else:
                            # only update previous ending index, if it is to the left of the current ending index
                            last_end = last_end if last_end >= end else end
        # mark the "last" field to add
        (fields_to_add[-1]).is_last = True
        return fields_to_add

    def __write_new_headings_row(self, reader, writer, fields_to_add):
        """ Writes a headings row into the new CSV template based on the fields to add, as well as corresponding slices
        from the original CSV template.

        :param reader: Instantiated reader object from the csv module that allows for iterating over the original CSV
        file.
        :param writer: Instantiated writer object from the csv module that allows writing to the new CSV file.
        :param fields_to_add: List of fields to add and optionally corresponding slices from the original CSV template.
        :return: Nothing.
        """
        headings_row = next(reader, None)
        new_csv_row = []
        for field_to_add in fields_to_add:
            new_csv_row += field_to_add.get_new_heading_slice(
                original_csv_row=headings_row,
                field_heading=self.get_col_heading_name(
                    model=field_to_add.model_name,
                    field=field_to_add.field_name
                )
            )
        # write row to the new CSV template
        writer.writerow(new_csv_row)

    def __write_new_data_rows(self, reader, writer, fields_to_add):
        """ Writes a headings row into the new CSV template based on the fields to add, as well as corresponding slices
        from the original CSV template.

        :param reader: Instantiated reader object from the csv module that allows for iterating over the original CSV
        file.
        :param writer: Instantiated writer object from the csv module that allows writing to the new CSV file.
        :param fields_to_add: List of fields to add and optionally corresponding slices from the original CSV template.
        :return: Nothing.
        """
        # cycle through original CSV template data rows and modify using fields to add and corresponding slices
        for row_num, original_csv_row in enumerate(reader):
            new_csv_row = []
            # cycle through the fields to add and corresponding slices from the original CSV template that
            # can be used to create a new CSV row
            for field_to_add in fields_to_add:
                new_csv_row += field_to_add.get_new_data_slice(
                    original_csv_row=original_csv_row,
                    auto_external_id=self.get_auto_external_id(
                        uuid=self.uuid,
                        group=field_to_add.group,
                        row_num=row_num + 1
                    ),
                    reference_auto_external_id=self.get_auto_external_id(
                        uuid=self.uuid,
                        group=field_to_add.reference_group,
                        row_num=row_num + 1
                    )
                )
            # write row to the new CSV template
            writer.writerow(new_csv_row)

    @handle_import_errors
    def convert_implicit_references(self):
        """ Converts implicit references between related models to be explicit using external IDs.

        Related models are any that are linked by foreign keys, one-to-one fields and many-to-many fields, even if those
        are not required, i.e. they are nullable.

        If implicit references are found in the CSV template, then it will be updated and the original overwritten.

        :return: Nothing.
        """
        if self.is_ready_for_import:
            new_csv_file = None
            file_changed = False
            filename = self.file.name
            decoded_string_content = self.__get_decoded_string_content()
            with StringIO(decoded_string_content) as read_string_io:
                reader = self.__get_csv_reader(string_io=read_string_io)
                # creates and populates data structures to store metadata used during the import such as models
                # involved, their fields, and those fields' types
                self.__make_import_metadata(reader=reader)
                # fields to add, in the format of: {
                # 'model_1': [(field_1, is_pk_1, rel_model_1), (field_2, is_pk_2, rel_model_2), ...],
                # 'model_2': [...],
                # ...
                # }
                cached_fields_to_add_by_model = self.__get_fields_to_convert_implicit_references()
                # number of data rows
                self._num_of_data_rows = len([1 for _ in reader])
                # if there are some fields to add
                if cached_fields_to_add_by_model:
                    # rewind the memory stream position, to read the heading row again
                    self.__rewind_io(io_to_rewind=read_string_io)
                    # list of CSV slice object instances that can be used to define a new CSV row
                    fields_to_add = self.get_fields_to_add(cached_fields_to_add_by_model=cached_fields_to_add_by_model)
                    # rebuild CSV using CSV slices
                    with StringIO() as write_string_io:
                        writer = self.__get_csv_writer(string_io=write_string_io)
                        self.__write_new_headings_row(reader=reader, writer=writer, fields_to_add=fields_to_add)
                        self.__write_new_data_rows(reader=reader, writer=writer, fields_to_add=fields_to_add)
                        # wrap the file
                        new_csv_file = ContentFile(write_string_io.getvalue().encode(self.csv_encoding))
                        file_changed = True
            # only re-save object if CSV template file has been changed to make explicit the implicit references
            if file_changed:
                file = getattr(self, 'file')
                file.save(f'mod_{filename}', new_csv_file)

    @staticmethod
    def get_col_heading_name(model, field):
        """ Retrieves the name of a column heading for the wholesale import tool template.

        :param model: Model for which to retrieve heading.
        :param field: Field in model for which to retrieve heading.
        :return: String representing column heading.
        """
        return f'{model}.{field}'

    def get_models_with_fields(self):
        """ Retrieves a list of tuples that represent the models and their corresponding fields that are intended for
        this import.

        Ensure that this is only called once the _metadata_by_model_name data structure has been populated.

        :return: List of tuples, where for each tuple:
                    [0] String representation of model name; and
                    [1] Iterable of field names for model.
        """
        return [
            (
                # string representation of model name
                model_name,
                # iterable of field names for model
                self._metadata_by_model_name[model_name][self.__model_fields_index]
            ) for model_name in self._metadata_by_model_name
        ]

    def get_num_of_data_rows(self):
        """ Retrieves the number of rows of data to be imported.

        Ensure that this is only called once the _num_of_data_rows attribute has been set during the conversion of
        implicit model references, i.e. in convert_implicit_references(...).

        :return: Number of rows of data to be imported, or None if not known.
        """
        return self._num_of_data_rows

    class Meta:
        db_table = '{d}wholesale_import'.format(d=settings.DB_PREFIX)
        verbose_name = _('wholesale import')
        verbose_name_plural = _('wholesale imports')
        ordering = ['-ended_timestamp', '-started_timestamp']


class WholesaleImportRecordManager(models.Manager):
    """ Manager for a single record that was imported or attempted to be imported through the wholesale import tool.

    """
    pass


class WholesaleImportRecord(Metable):
    """ Single record that was imported or attempted to be imported through the wholesale import tool.

    Attributes:
        :wholesale_import (fk): Wholesale import to which this record belongs.
        :row_num (int): Row number in template to which this record corresponds.
        :model_name (str): Name of model to which this record was imported.
        :instance_pk (int): Primary key in database for model instance to which this record was imported.
        :errors (str): Errors that may have been encountered during the import attempt.
    """
    wholesale_import = models.ForeignKey(
        WholesaleImport,
        on_delete=models.CASCADE,
        related_name='wholesale_import_records',
        related_query_name='wholesale_import_record',
        null=False,
        blank=False,
        verbose_name=_('Wholesale import'),
        help_text=_('Wholesale import to which this record belongs.')
    )

    row_num = models.PositiveBigIntegerField(
        null=False,
        blank=False,
        verbose_name=_('Row number'),
        help_text=_('Row number in template to which this record corresponds.')
    )

    model_name = models.CharField(
        null=False,
        blank=False,
        max_length=settings.MAX_NAME_LEN,
        verbose_name=_('Model'),
        help_text=_('Name of model to which this record corresponds.')
    )

    instance_pk = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Primary key'),
        help_text=_('Primary key in database for model instance to which this record was imported.')
    )

    errors = models.TextField(
        null=False,
        blank=True,
        default='',
        verbose_name=_('Errors'),
        help_text=_('Errors that may have been encountered during the import attempt. '
                    'Blank if no errors were encountered.'),
    )

    objects = WholesaleImportRecordManager()

    def __str__(self):
        """ Defines string representation for a single record that was imported or attempted to be imported through
        the wholesale import tool.

        :return: String representation for a single record that was imported or attempted to be imported through the
        wholesale import tool.
        """
        return f'{self.get_verbose_name()} #{self.pk}'

    class Meta:
        db_table = '{d}wholesale_import_record'.format(d=settings.DB_PREFIX)
        verbose_name = _('wholesale import record')
        verbose_name_plural = _('wholesale import records')
        ordering = ['-wholesale_import', 'model_name', 'row_num']
