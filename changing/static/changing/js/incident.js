/**
 * @file Functionality for adding and editing incidents through the data management tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires jqueryui
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingIncidentDef = {};

    /**
	 * True when an existing incident is being edited, false when a new incident is being created. Set when page is initialized.
	 */
	var _isEditing = false;

    /**
     * JQuery selector for icon to add a new location.
     */
    var _newLocSelector = ".newloclink";

    /**
     * Relative URL through which new locations can be added.
     */
    var _newLocationUrl = null;

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of groupings.
	 */
	var _getGroupingsUrl = null;

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of persons.
	 */
	var _getPersonsUrl = null;

    /**
	 * JQuery selector for input used to search for persons on person incident forms.
	 */
    var _personSearchInputSelector = ".personname";

    /**
	 * JQuery selector for the hidden element containing the person ID on person incident forms.
	 */
    var _personIdSelector = ".person";

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
     * Called to initialize the person incident forms, including adding new and deleting existing forms.
    */
    function _initPersonIncidentForms() {
        var formPrefix = "personincidents";
        var emptySelector = "#emptypersonincident";
        var newContSelector = "<div />";

        // icon to add new person incident forms
        var elem = $("#newpersonincident");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                formPrefix, /* formPrefix */
                emptySelector, /* emptySelector */
                _initPersonIncidentForm, /* onAddFunc */
                newContSelector /* newContSelector */
            );
        });

        // icons to remove existing person incident forms
        $(".personincidentform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonIncidentForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
        // container for suggested persons
        var suggPersonsCont = $("#sggper");
        if (suggPersonsCont.length > 0) {
            suggPersonsCont.find("i.sgg").each(function (i, elem) {
                var addSuggPerson = $(elem);
                var personPk = addSuggPerson.data("id");
                var personName = addSuggPerson.data("name");
                addSuggPerson.one("click", function () {
                    var liToDelete = addSuggPerson.closest("li");
                    Fdp.Common.fadeOut(
                        liToDelete, /* elemToFadeOut */
                        function () { liToDelete.remove(); } /* onCompleteFunc */
                    );
                    Fdp.Common.addInlineForm(
                        formPrefix, /* formPrefix */
                        emptySelector, /* emptySelector */
                        _getInitPersonIncidentFormFromPersonSuggestionFunc(
                            personPk, /* personPk */
                            personName /* personName */
                        ), /* onAddFunc */
                        newContSelector /* newContSelector */
                    );
                });
            });
        }
    };

    /**
     * Called to initialize the grouping incident forms, including adding new and deleting existing forms.
    */
    function _initGroupingIncidentForms() {
        // icon to add new grouping incident forms
        var elem = $("#newgroupingincident");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "groupingincidents", /* formPrefix */
                "#emptygroupingincident", /* emptySelector */
                _initGroupingIncidentForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing grouping incident forms
        $(".groupingincidentform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initGroupingIncidentForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Marks a person incident form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person incident form to delete.
    */
    function _delPersonIncidentForm(id) {
        Fdp.Common.delInlineForm(
            "personincidents", /* formPrefix */
            id, /* id */
            ".personincidentform" /* parentSelector */
        );
    };

    /**
     * Marks a grouping incident form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of grouping incident form to delete.
    */
    function _delGroupingIncidentForm(id) {
        Fdp.Common.delInlineForm(
            "groupingincidents", /* formPrefix */
            id, /* id */
            ".groupingincidentform" /* parentSelector */
        );
    };

    /**
     * Retrieves a function called to initialize a person incident form created from a suggested person link.
     * @param {number} personPk - Primary key used to identify person for which person incident form is being created.
     * @param {string} personName - Name of person for which person incident form is being created.
     * @returns {function} Function called to initialize a person incident form created from a suggested person link.
    */
    function _getInitPersonIncidentFormFromPersonSuggestionFunc(personPk, personName) {

        var personSearchInputSelector = _personSearchInputSelector;
        var personIdSelector = _personIdSelector;

        /**
         * Initializes a person incident form created from a suggested person link.
         * @param {Object} formContainer - Element containing person incident form. Must be wrapped in JQuery object.
        */
        return function (formContainer) {

            // set person name in search field
            var personSearchInput = Fdp.Common.getAutocompleteSearchElem(
                formContainer /* formContainer */,
                personSearchInputSelector /* selector */);
            personSearchInput.val(personName);
            // set person id in hidden field
            var personIdInput = Fdp.Common.getAutocompleteIdElem(
                formContainer /* formContainer */,
                personIdSelector /* selector */
            );
            personIdInput.val(personPk);

            // initialize the form
            _initPersonIncidentForm(formContainer /* formContainer */);
        };

    };

    /**
     * Initializes a person incident form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person incident form. Must be wrapped in JQuery object.
    */
    function _initPersonIncidentForm(formContainer) {
        var delBtn = formContainer.find(".delperson");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonIncidentForm(id /* id */ );
        });
        var personSearchInput = Fdp.Common.getAutocompleteSearchElem(
            formContainer /* formContainer */,
            _personSearchInputSelector /* selector */
        );
        var personIdInput = Fdp.Common.getAutocompleteIdElem(
            formContainer /* formContainer */,
            _personIdSelector /* selector */
        );
        // person searching with autocomplete
        Fdp.Common.initAutocomplete(
            personSearchInput, /* searchInputElem */
            personIdInput, /* idInputElem */
            _getPersonsUrl, /* ajaxUrl */
            "personac" /* extraCssClass */
        );
        // copy hidden errors to the corresponding visible input
        Fdp.Common.copyErrorsFromInput(
            personIdInput, /* fromInput */
            personSearchInput /* toInput */
        );
    };

    /**
     * Initializes a grouping incident form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing grouping incident form. Must be wrapped in JQuery object.
    */
    function _initGroupingIncidentForm(formContainer) {
        var delBtn = formContainer.find(".delgrouping");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delGroupingIncidentForm(id /* id */);
        });
        var groupingSearchInput = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".groupingname" /* selector */);
        var groupingIdInput = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".grouping" /* selector */);
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
    };

    /**
     * Initializes interactivity for interface elements for adding and editing incident through the data management tool. Should be called when DOM is ready.
     * @param {boolean} isEditing - True if incident already exists, and we are editing it, false otherwise.
     * @param {string} getPersonsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of persons.
     * @param {string} getGroupingsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of groupings.
     * @param {string} newLocationUrl - Relative URL through which new locations can be added.
     * @param {string} popupKey - Queryset GET parameter used to indicate whether incident form is being rendered as a popup.
     * @param {string} popupValue - Queryset GET parameter value used to indicate whether incident form is being rendered as a popup.
     * @param {string} popupIdKey - Queryset GET parameter used to indicate the unique identifier for the form that is being rendered as a popup.
     * @param {string} popupField - Name of popup field that will be used to contain the unique identifier for the form when it is rendered as a popup.
     */
	changingIncidentDef.init = function (isEditing, getPersonsUrl, getGroupingsUrl, newLocationUrl, popupKey, popupValue, popupIdKey, popupField) {

        _isEditing = isEditing;
        _getPersonsUrl = getPersonsUrl;
        _getGroupingsUrl = getGroupingsUrl;
        _newLocationUrl = newLocationUrl;

        // disable enter key for page
        Fdp.Common.disableEnterKey();

        // ability to add new locations through wizard
        var emptyLocLink = $("#emptynewlocation").children().clone();
        var locationInput = $(".location");
        locationInput.after(emptyLocLink);
        var newLocBtn = $(_newLocSelector);
        var uniqueId = "newlocation";
        newLocBtn.on("click", function (e) {
            if (!w[Fdp.Common.windowFuncs]) { w[Fdp.Common.windowFuncs] = {}; }
            // close all windows opened previously through new location button
            Fdp.Common.closePopups(uniqueId /* uniqueId */);
            w[Fdp.Common.windowFuncs][uniqueId] = function (locationId, locationName) {
                Fdp.Common.closePopups(uniqueId /* uniqueId */);
                locationInput.append($("<option>", { value: locationId, text: locationName}));
                locationInput.val(locationId);
            };
            Fdp.Common.openPopup(
                _newLocationUrl, /* url */
                uniqueId, /* uniqueId */
                true /* makeAbsolute */
            );
            e.preventDefault();
        });

        // initialize adding new and removing existing person incidents
        _initPersonIncidentForms();

        // initialize adding new and removing existing grouping incidents
        _initGroupingIncidentForms();

        // initialize date pickers
        _initDatePickers(null /* containerSelector */);

        // initialize multiple select elements
        Fdp.Common.initPassiveSelect2Elems(".multiselect" /* selector */);
        // initialize location selector
        Fdp.Common.initPassiveSelect2Elems("#id_location" /* selector */);

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

        // form is being rendered as a popup
        if (Fdp.Common.isPopup(popupKey /* popupKey */) === true) {
            Fdp.Common.addPopupIdToForm(
                w, /* windowElem */
                popupValue, /* popupValue */
                popupIdKey, /* popupIdKey */
                popupField, /* popupField */
                $("form fieldset") /* formInPopup */
            );
        }
        // form is not being rendered as a popup
        else {
            Fdp.Common.nullifyPopupIdInForm(popupField /* popupField */)
        }

	};

	fdpDef.ChangingIncident = changingIncidentDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
