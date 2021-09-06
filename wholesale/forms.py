from django import forms
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.db.models import ManyToManyField, ForeignKey, OneToOneField, ManyToManyRel, ManyToOneRel, OneToOneRel
from inheritable.models import AbstractConfiguration
from .models import WholesaleImport, ModelHelper
from graphlib.graphlib import TopologicalSorter


class WholesaleTemplateForm(forms.Form):
    """ Synchronous form for the wholesale import tool that is submitted to generate a template specific to a
    combination of the data model.

    Fields:
        models (list): List of models select by the user for which to generate a wholesale import tool template.

    """
    models = forms.MultipleChoiceField(
        required=True,
        label=_('Models'),
        choices=[],
        help_text=_('Combination of models for which to generate template')
    )
    #: Adds a CSS class attribute to the SELECT element so that it can be easily identified for wrapping in the Select2
    # package.
    models.widget.attrs.update({'class': 'multiselect'})

    def __init__(self, *args, **kwargs):
        """ Defines the list of all possible models for which templates can be generated.

        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        relevant_models = ModelHelper.get_relevant_models()
        whitelisted_models = sorted(
            [
                ModelHelper.get_str_for_cls(model_class=m) for m in relevant_models
                if ModelHelper.get_str_for_cls(model_class=m) in AbstractConfiguration.whitelisted_wholesale_models()
            ]
        )
        self.fields['models'].choices = [(m, m) for m in whitelisted_models]

    def clean_models(self):
        """ Ensures that the submitted list of models for which to generate a template adheres to the whitelist.

        :return: List of whitelisted models.
        """
        models = self.cleaned_data['models']
        for model in models:
            if model not in AbstractConfiguration.whitelisted_wholesale_models():
                raise ValidationError(_(f'Model {model} is not whitelisted for the wholesale import tool'))
        return models

    @staticmethod
    def __get_dependent_model_classes(model_class):
        """ Retrieves the model classes upon which the specified model class depends.

        :param model_class: Model class for which to retrieve dependencies.
        :return: List of model classes upon which specified model class depends.
        """
        return [
            f.remote_field.model
            for f in ModelHelper.get_fields(model=model_class)
            if (
                # field for relation must be defined on the model itself
                (f.many_to_many and isinstance(f, ManyToManyField))
                or (f.many_to_one and isinstance(f, ForeignKey))
                or (f.one_to_one and isinstance(f, OneToOneField))
            ) and (
                # field cannot reference model it is defined on
                model_class != f.remote_field.model
            )
        ]

    def __load_model_classes(self, models):
        """ Loads the model classes, and in the process, determines the apps to which each model belongs.

        :param models: List of strings that defines the models for which to load model classes.
        :return: List of tuples, where in each tuple:
                    [0] App name to which model belongs, as a string;
                    [1] Model name as a string;
                    [2] Model class; and
                    [3] List of model classes upon which model depends.
        """
        models_with_apps_and_classes = []
        for model in models:
            app_name = ModelHelper.get_app_name(model=model)
            # model is in none of the expected apps
            if not app_name:
                raise Exception(_('Wholesale import tool model is whitelisted but does not '
                                  'appear in the sourcing, core or supporting apps'))
            # load the model class
            model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model)
            # add the tuple to the list
            models_with_apps_and_classes.append(
                (
                    app_name,
                    model,
                    model_class,
                    self.__get_dependent_model_classes(model_class=model_class)
                )
            )
        return models_with_apps_and_classes

    @staticmethod
    def __record_model_index(index, model_class_name, dict_of_list_indices, cache_for_indices):
        """ Records the model's index in the list using the dependency dictionary and cache dictionary.

        :param index: String representing index of model class in list.
        :param model_class_name: String representing name of model class.
        :param dict_of_list_indices: Dictionary mapping dependencies using indices from the list.
        :param cache_for_indices: Cache dictionary mapping model classes to their respective indices.
        :return: Nothing.
        """
        # not yet added to dictionary
        if index not in dict_of_list_indices:
            dict_of_list_indices[index] = set()
            cache_for_indices[model_class_name] = index

    def __get_model_dependencies(self, models_with_apps_and_classes):
        """ Retrieves a dictionary that maps the dependencies between the different model classes.

        :param models_with_apps_and_classes: List of tuples where:
                    [0] App name to which model belongs, as a string;
                    [1] Model name as a string;
                    [2] Model class; and
                    [3] List of model classes upon which model depends.
        :return: Dictionary of dependencies, where the keys are indices of the models from the list, and the values are
        sets of dependent model indices.
        """
        # cache mapping model classes to their respective indices
        cache_for_indices = {}
        # dictionary that maps dependencies using the indices from the list
        dict_of_list_indices = {}
        for i, model_tuple in enumerate(models_with_apps_and_classes):
            str_i = str(i)
            self.__record_model_index(
                index=str_i,
                model_class_name=ModelHelper.get_str_for_cls(model_class=model_tuple[2]),
                dict_of_list_indices=dict_of_list_indices,
                cache_for_indices=cache_for_indices
            )
            # cycle through the models upon which this model depends
            for dependent_model_class in model_tuple[3]:
                dependent_model_class_name = ModelHelper.get_str_for_cls(model_class=dependent_model_class)
                # index for this model is already cached
                if dependent_model_class_name in cache_for_indices:
                    dependent_str_i = cache_for_indices[dependent_model_class_name]
                # find index for this model
                else:
                    dependent_str_i = None
                    for j, dependent_model_tuple in enumerate(models_with_apps_and_classes):
                        # this is the model class we are looking for
                        if ModelHelper.get_str_for_cls(
                                model_class=dependent_model_tuple[2]
                        ) == dependent_model_class_name:
                            str_j = str(j)
                            self.__record_model_index(
                                index=str_j,
                                model_class_name=dependent_model_class_name,
                                dict_of_list_indices=dict_of_list_indices,
                                cache_for_indices=cache_for_indices
                            )
                            # stop the search
                            dependent_str_i = str_j
                            break
                # add dependency to set if it is relevant
                if dependent_str_i is not None:
                    (dict_of_list_indices[str_i]).add(dependent_str_i)
        return dict_of_list_indices

    def __order_model_classes(self, models_with_apps_and_classes):
        """ Attempts to order the list of models so that their dependencies such as foreign keys are respected during
        the order of import.

        This is not an guaranteed ordering: some model combinations may generate incorrect ordering.

        :param models_with_apps_and_classes: List of tuples where:
                    [0] App name to which model belongs, as a string;
                    [1] Model name as a string;
                    [2] Model class; and
                    [3] List of model classes upon which model depends.
        :return: List of model classes that is attempted to be ordered to respect their dependencies.
        """
        #: TODO: Once Python 3.9 is supported, the graphlib module can be added.
        #: TODO: See: https://docs.python.org/3/library/graphlib.html
        #: TODO: Also, the graphlib backport can be removed.
        #: TODO: See: https://pypi.org/project/graphlib-backport/
        # dictionary will be in the form of: {'3': {'2', '7'}, '1': {}, '2': {'7'}, ....}
        dict_of_list_indices = self.__get_model_dependencies(models_with_apps_and_classes=models_with_apps_and_classes)
        # perform topological sorting
        topological_sorter = TopologicalSorter(graph=dict_of_list_indices)
        # retrieve the order list
        sorted_indices_list = list(topological_sorter.static_order())
        # ordered list of model classes
        return [models_with_apps_and_classes[int(index)][2] for index in sorted_indices_list]

    @staticmethod
    def __get_col_heading_name(model, field):
        """ Retrieves the name of a column heading for the wholesale import tool template.

        :param model: Model for which to retrieve heading.
        :param field: Field in model for which to retrieve heading.
        :return: String representing column heading.
        """
        return f'{model}.{field}'

    def __get_column_headings(self, ordered_model_classes):
        """ Retrieves the column headings for the wholesale import tool template for a particular combination of the
        data model.

        :param ordered_model_classes: List of model classes that have been ordered from left to right with respect to
        their dependencies.
        :return: List of column headings.
        """
        col_headings = []
        # cycle through ordered models
        for model_class in ordered_model_classes:
            # cycle through fields for model
            for f in ModelHelper.get_fields(model=model_class):
                if not (
                    # exclude relations that are not defined on the model
                    (
                        f.is_relation and (
                            isinstance(f, OneToOneRel) or isinstance(f, ManyToOneRel) or isinstance(f, ManyToManyRel)
                        )
                    )
                    or
                    # exclude blacklisted fields
                    (
                        f.name in AbstractConfiguration.blacklisted_wholesale_fields()
                    )
                ):
                    model = ModelHelper.get_str_for_cls(model_class=model_class)
                    field = f.name
                    col_headings.append(self.__get_col_heading_name(model=model, field=field))
                    # if this is the primary key, or a many-to-many field, or a foreign key, or a one-to-one field
                    # add possibility to specify external id
                    if field == 'id' or f.many_to_many or f.many_to_one or f.one_to_one:
                        col_headings.append(
                            self.__get_col_heading_name(
                                model=model,
                                field=f'{field}{WholesaleImport.external_id_suffix}'
                            )
                        )
        return col_headings

    def get_wholesale_template_headings(self):
        """ Retrieves a list of column headings for the wholesale import tool template that was generated for a
        specific combination of the data model specified by the instance of the for.

        :return: List of column headings.
        """
        # assume self.clean_models(...) has already ensured only whitelisted models are included
        models = self.cleaned_data['models']
        # identify the apps for the models
        models_with_apps_and_classes = self.__load_model_classes(models=models)
        # order models to respect dependencies such as foreign keys during import
        ordered_model_classes = self.__order_model_classes(models_with_apps_and_classes=models_with_apps_and_classes)
        # retrieve the columns for the wholesale import tool template
        col_headings = self.__get_column_headings(ordered_model_classes=ordered_model_classes)
        return col_headings


class WholesaleStartImportForm(forms.ModelForm):
    """ Synchronous form for the wholesale import tool that is submitted to start an import process.

    """
    class Meta:
        model = WholesaleImport
        fields = ['file', 'action', 'before_import', 'on_error']
