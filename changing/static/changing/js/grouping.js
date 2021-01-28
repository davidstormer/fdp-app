/**
 * @file Functionality for adding and editing groupings through the data management tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires jqueryui
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingGroupingDef = {};

    /**
	 * True when an existing grouping is being edited, false when a new grouping is being created. Set when page is initialized.
	 */
	var _isEditing = false;

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of groupings.
	 */
	var _getGroupingsUrl = null;

    /**
     * Called to initialize the grouping alias forms, including adding new and deleting existing forms.
    */
    function _initGroupingAliasForms() {
        // icon to add new alias forms
        var elem = $("#newgroupingalias");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "aliases", /* formPrefix */
                "#emptygroupingalias", /* emptySelector */
                _initGroupingAliasForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing grouping alias forms
        $(".groupingaliasform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initGroupingAliasForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the grouping relationships forms, including adding new and deleting existing forms.
    */
    function _initGroupingRelationshipForms() {
        // icon to add new relationship forms
        var elem = $("#newgroupingrelationship");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "relationships", /* formPrefix */
                "#emptygroupingrelationship", /* emptySelector */
                _initGroupingRelationshipForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });
        // icons to remove existing grouping relationship forms
        $(".groupingrelationshipform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initGroupingRelationshipForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Marks a grouping alias form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of grouping alias form to delete.
    */
    function _delGroupingAliasForm(id) {
        Fdp.Common.delInlineForm(
            "aliases", /* formPrefix */
            id, /* id */
            ".groupingaliasform" /* parentSelector */
        );
    };

    /**
     * Marks a grouping relationship form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of grouping relationship form to delete.
    */
    function _delGroupingRelationshipForm(id) {
        Fdp.Common.delInlineForm(
            "relationships", /* formPrefix */
            id, /* id */
            ".groupingrelationshipform" /* parentSelector */
        );
    };

    /**
     * Initializes a grouping alias form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing grouping alias form. Must be wrapped in JQuery object.
    */
    function _initGroupingAliasForm(formContainer) {
        var delBtn = formContainer.find(".delalias");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delGroupingAliasForm(
                id /* id */
            );
        });
    };

    /**
     * Toggle the input fields for a grouping relationship between a subject and object perspective.
     * @param {Object} aInput - The input to be faded out. Must be wrapped in JQuery object.
     * @param {Object} bInput - The input to be faded in. Must be wrapped in JQuery object.
     * @param {Object} aIcon - The icon to be faded out. Must be wrapped in JQuery object.
     * @param {Object} bIcon - The icon to be faded in. Must be wrapped in JQuery object.
    */
    function _changeGroupingRelationshipOrder(aInput, bInput, aIcon, bIcon) {
        Fdp.Common.fadeOut(
            aInput, /* elemToFadeOut */
            function () {
                Fdp.Common.fadeIn(
                    bInput, /* elemToFadeIn */
                    null /* onCompleteFunc */
                );
            } /* onCompleteFunc */
        );
        Fdp.Common.fadeOut(
            aIcon, /* elemToFadeOut */
            function () {
                Fdp.Common.fadeIn(
                    bIcon, /* elemToFadeIn */
                    null /* onCompleteFunc */
                );
            } /* onCompleteFunc */
        );
    };

    /**
     * Called to handle an icon click event switching from subject grouping relationship to object grouping relationship, or vice-versa.
     * @param {Object} aId - The input element that will contain the ID value selected by the user. Must be wrapped in JQuery object.
     * @param {Object} bId - The input element for the ID that will be empty (and faded out). Must be wrapped in JQuery object.
     * @param {Object} aName - The input element that will contain the string value selected by the user. Must be wrapped in JQuery object.
     * @param {Object} bName - The input element for the string that will empty (and faded out). Must be wrapped in JQuery object.
     * @param {Object} aIcon - The icon to be faded in. Must be wrapped in JQuery object.
     * @param {Object} bIcon - The icon to be faded out. Must be wrapped in JQuery object.
    */
    function _changeGroupingRelationshipFromIcon(aId, bId, aName, bName, aIcon, bIcon) {
        aId.val(bId.val());
        bId.val("");
        aName.val(bName.val());
        bName.val("");
        _changeGroupingRelationshipOrder(
            bName, /* aInput */
            aName, /* bInput */
            bIcon, /* aIcon */
            aIcon /* bIcon */
        );
    };

    /**
     * Initializes a grouping relationship form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing grouping relationship form. Must be wrapped in JQuery object.
    */
    function _initGroupingRelationshipForm(formContainer) {
        var delBtn = formContainer.find(".delrelationship");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delGroupingRelationshipForm(
                id /* id */
            );
        });
        // initialize newly added date pickers
        _initDatePickers(".groupingrelationshipform" /* containerSelector */);
        // initialize relationship
        var subjectId = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".subjectid" /* selector */);
        var objectId = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".objectid" /* selector */);
        var subjectName = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".subjectname" /* selector */);
        var objectName = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".objectname" /* selector */);
        var subjectIcon = formContainer.find(".subjectrelicon");
        var objectIcon = formContainer.find(".objectrelicon");
        // subject grouping searching with autocomplete
        Fdp.Common.initAutocomplete(
            subjectName, /* searchInputElem */
            subjectId, /* idInputElem */
            _getGroupingsUrl, /* ajaxUrl */
            "groupingac" /* extraCssClass */
        );
        // object grouping searching with autocomplete
        Fdp.Common.initAutocomplete(
            objectName, /* searchInputElem */
            objectId, /* idInputElem */
            _getGroupingsUrl, /* ajaxUrl */
            "groupingac" /* extraCssClass */
        );
        // subject grouping defined
        if (subjectName.val()) {
            _changeGroupingRelationshipOrder(
                objectName, /* aInput */
                subjectName, /* bInput */
                objectIcon, /* aIcon */
                subjectIcon /* bIcon */
            );
        }
        // object grouping defined (or this a new relationship, so nothing is defined)
        else {
            _changeGroupingRelationshipOrder(
                subjectName, /* aInput */
                objectName, /* bInput */
                subjectIcon, /* aIcon */
                objectIcon /* bIcon */
            );
        }
        subjectIcon.on("click", function () {
            _changeGroupingRelationshipFromIcon(
                objectId, /* aId */
                subjectId, /* bId */
                objectName, /* aName */
                subjectName, /* bName */
                objectIcon, /* aIcon */
                subjectIcon /* bIcon */
            );
        });
        objectIcon.on("click", function () {
            _changeGroupingRelationshipFromIcon(
                subjectId, /* aId */
                objectId, /* bId */
                subjectName, /* aName */
                objectName, /* bName */
                subjectIcon, /* aIcon */
                objectIcon /* bIcon */
            );
        });
        // copy hidden errors to the corresponding visible input
        Fdp.Common.copyErrorsFromInput(
            subjectId, /* fromInput */
            subjectName /* toInput */
        );
        // copy hidden errors to the corresponding visible input
        Fdp.Common.copyErrorsFromInput(
            objectId, /* fromInput */
            objectName /* toInput */
        );
    };

    /**
     * Function called when a date is selected through the JQuery UI Datepicker.
     * @param {string} selectedDate - Date was selected in the Datepicker plugin. Will be in the format of "mm/dd/yyyy".
     * @param {Object} datepickerInstance - Instance of Datepicker through which date was selected.
    */
    function _onDateSelected(selectedDate, datepickerInstance) {
        var span = $(datepickerInstance.input);
        var inputs = span.siblings("input");
        // single date component
        if (inputs.length === 1) {
            var input = inputs.first();
            input.val(selectedDate);
        }
        // multiple date components
        else {
            var monthInput = span.siblings(".datemonth").first();
            var dayInput = span.siblings(".dateday").first();
            var yearInput = span.siblings(".dateyear").first();
            // format of date assumed to be mm/dd/yyyy
            var dateComponents = selectedDate.split("/");
            monthInput.val(dateComponents[0]);
            dayInput.val(dateComponents[1]);
            yearInput.val(dateComponents[2]);
        }
    };

    /**
     * Initializes all JQuery UI Datepickers.
     * @param {string} containerSelector - JQuery selector text used to identify the container in which the Datepickers should be initialized.
     Set to null if all Datepickers on page should be initialized.
    */
    function _initDatePickers(containerSelector) {
        Fdp.Common.initDatePickers(
            _onDateSelected, /* onDateSelectFunc */
            containerSelector /* containerSelector */
        );
    };

    /**
     * Initializes interactivity for interface elements for adding and editing grouping through the data management tool. Should be called when DOM is ready.
     * @param {boolean} isEditing - True if grouping already exists, and we are editing it, false otherwise.
     * @param {string} getGroupingsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of groupings.
     */
	changingGroupingDef.init = function (isEditing, getGroupingsUrl) {

        _isEditing = isEditing;
        _getGroupingsUrl = getGroupingsUrl;

        // disable enter key for page
        Fdp.Common.disableEnterKey();

        // belongs to field in grouping details
        var groupingFormContainer = $(".groupingdetailsform");
        var groupingSearchInput = Fdp.Common.getAutocompleteSearchElem(groupingFormContainer /* formContainer */, ".groupingname" /* selector */);
        var groupingIdInput = Fdp.Common.getAutocompleteIdElem(groupingFormContainer /* formContainer */, ".grouping" /* selector */);
        // grouping searching with autocomplete
        Fdp.Common.initAutocomplete(
            groupingSearchInput, /* searchInputElem */
            groupingIdInput, /* idInputElem */
            _getGroupingsUrl, /* ajaxUrl */
            "groupingac" /* extraCssClass */
        );
        // copy hidden errors to the corresponding visible input
        Fdp.Common.copyErrorsFromInput(
            groupingIdInput, /* fromInput */
            groupingSearchInput /* toInput */
        );

        // initialize adding new and removing existing grouping alias
        _initGroupingAliasForms();

        // initialize adding new and removing existing grouping relationship
        _initGroupingRelationshipForms();

        // initialize date pickers
        _initDatePickers(
            null /* containerSelector */
        );

        // initialize multiple select elements
        Fdp.Common.initPassiveSelect2Elems(".multiselect" /* selector */);

        // init expandable / collapsible sections
        var collapsibleButtons = "button.collapsible";
        $(collapsibleButtons).each(function (i, elem) {
            var button = $(elem);
            var div = button.next("div.collapsible");
            Fdp.Common.initCollapsible(
                button, /* button */
                div, /* div */
                null, /* onStart */
                null/* onComplete */
            );
        });

	};

	fdpDef.ChangingGrouping = changingGroupingDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
