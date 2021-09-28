from django import forms
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
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

    @staticmethod
    def __get_relevant_models_in_allowlist():
        """ Retrieves a list of relevant models in the allowlist.

        :return: List strings representing model names.
        """
        relevant_models = ModelHelper.get_relevant_models()
        models_in_allowlist = sorted(
            [
                ModelHelper.get_str_for_cls(model_class=m) for m in relevant_models
                if ModelHelper.get_str_for_cls(model_class=m) in AbstractConfiguration.models_in_wholesale_allowlist()
            ]
        )
        return models_in_allowlist

    def __init__(self, *args, **kwargs):
        """ Defines the list of all possible models for which templates can be generated.

        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        relevant_models_in_allowlist = self.__get_relevant_models_in_allowlist()
        self.fields['models'].choices = [(m, m) for m in relevant_models_in_allowlist]

    def clean_models(self):
        """ Ensures that the submitted list of models for which to generate a template adheres to the allowlist.

        :return: List of models in the allowlist.
        """
        models = self.cleaned_data['models']
        for model in models:
            if model not in AbstractConfiguration.models_in_wholesale_allowlist():
                raise ValidationError(_(f'Model {model} is not in the allowlist for the wholesale import tool'))
        return models

    @staticmethod
    def __get_dependent_model_classes(model_class):
        """ Retrieves the model classes upon which the specified model class depends.

        :param model_class: Model class for which to retrieve dependencies.
        :return: List of model classes upon which specified model class depends.
        """
        return [
            field.remote_field.model
            for field in ModelHelper.get_fields(model=model_class)
            if ModelHelper.is_field_linked_to_another_model(model=model_class, field=field)
        ]

    @classmethod
    def __load_model_classes(cls, models):
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
                raise Exception(_('Wholesale import tool model is in the allowlist but does not '
                                  'appear in the sourcing, core or supporting apps'))
            # load the model class
            model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model)
            # add the tuple to the list
            models_with_apps_and_classes.append(
                (
                    app_name,
                    model,
                    model_class,
                    cls.__get_dependent_model_classes(model_class=model_class)
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

    @classmethod
    def __get_model_dependencies(cls, models_with_apps_and_classes):
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
            cls.__record_model_index(
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
                            cls.__record_model_index(
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

    @classmethod
    def __order_model_classes(cls, models_with_apps_and_classes):
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
        dict_of_list_indices = cls.__get_model_dependencies(models_with_apps_and_classes=models_with_apps_and_classes)
        # perform topological sorting
        topological_sorter = TopologicalSorter(graph=dict_of_list_indices)
        # retrieve the order list
        sorted_indices_list = list(topological_sorter.static_order())
        # ordered list of model classes
        return [models_with_apps_and_classes[int(index)][2] for index in sorted_indices_list]

    @classmethod
    def __get_column_headings(cls, ordered_model_classes):
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
                    ModelHelper.is_field_a_relation(field=f)
                    or
                    # exclude denylist fields
                    f.name in AbstractConfiguration.fields_in_wholesale_denylist()
                ):
                    model = ModelHelper.get_str_for_cls(model_class=model_class)
                    # primary key fields are automatically converted to external ID fields, and are therefore excluded
                    # from the generated templates; they are still allowed to be imported
                    field = f.name if f.name != 'id' else f'{f.name}{WholesaleImport.external_id_suffix}'
                    col_headings.append(WholesaleImport.get_col_heading_name(model=model, field=field))
                    # if this is the primary key, or a many-to-many field, or a foreign key, or a one-to-one field
                    # add possibility to specify external id
                    if field == 'id' or f.many_to_many or f.many_to_one or f.one_to_one:
                        col_headings.append(
                            WholesaleImport.get_col_heading_name(
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
        # assume self.clean_models(...) has already ensured only models in the allowlist are included
        models = self.cleaned_data['models']
        # identify the apps for the models
        models_with_apps_and_classes = self.__load_model_classes(models=models)
        # order models to respect dependencies such as foreign keys during import
        ordered_model_classes = self.__order_model_classes(models_with_apps_and_classes=models_with_apps_and_classes)
        # retrieve the columns for the wholesale import tool template
        col_headings = self.__get_column_headings(ordered_model_classes=ordered_model_classes)
        return col_headings

    @classmethod
    def __get_related_models_for_model(cls, model_name, relevant_models_in_allowlist):
        """ Retrieves list of models related to a particular model.

        A related model is a model that links to the model in question such as through a foreign key, one-to-one field
        or many-to-many field.

        Each related model must also be a member of the relevant models in the allowlist.

        :param model_name: Name of model for which to retrieve related models.
        :param relevant_models_in_allowlist: List of all relevant and model names in the allowlist.
        :return: List of related models.
        """
        app_name = ModelHelper.get_app_name(model=model_name)
        model_class = ModelHelper.get_model_class(app_name=app_name, model_name=model_name)
        fields = ModelHelper.get_fields(model=model_class)
        related_model_names = []
        for field in fields:
            # field is a relation
            if ModelHelper.is_field_a_relation(field=field):
                related_model_class = field.related_model
                related_model_name = ModelHelper.get_str_for_cls(model_class=related_model_class)
                # related model is in relevant models in the allowlist
                if related_model_name in relevant_models_in_allowlist:
                    related_model_names.append(related_model_name)
        return related_model_names

    @classmethod
    def get_model_relations(cls):
        """ Retrieves a dictionary mapping models to their model relations.

        :return: Dictionary with keys as model names, and values as lists of related models.
        """
        relevant_models_in_allowlist = cls.__get_relevant_models_in_allowlist()
        return {
            model_name: cls.__get_related_models_for_model(
                model_name=model_name,
                relevant_models_in_allowlist=relevant_models_in_allowlist
            ) for model_name in relevant_models_in_allowlist
        }


class WholesaleCreateImportForm(forms.ModelForm):
    """ Synchronous form for the wholesale import tool that is submitted to create a batch of data that can eventually
    be imported.

    """
    class Meta:
        model = WholesaleImport
        fields = ['file', 'action']


class WholesaleStartImportForm(forms.Form):
    """ Synchronous form for the wholesale import tool that is submitted to start importing a batch of data.

    Fields:
        None.

    """
    pass
