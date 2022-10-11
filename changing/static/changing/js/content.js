/**
 * @file Functionality for adding and editing content through the data management tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires jqueryui
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingContentDef = {};

    /**
	 * True when an existing content is being edited, false when a new content is being created. Set when page is initialized.
	 */
	var _isEditing = false;

    /**
     * JQuery selector for icon to add a new attachment.
     */
    var _newAttSelector = ".newattlink";

    /**
     * JQuery selector for icon to add a new incident.
     */
    var _newIncSelector = ".newinclink";

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of persons.
	 */
	var _getPersonsUrl = null;

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of attachments.
	 */
	var _getAttachmentsUrl = null;

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of incidents.
	 */
	var _getIncidentsUrl = null;

    /**
     * Relative URL through which new attachments can be added.
     */
    var _newAttachmentUrl = null;

    /**
     * Relative URL through which new incidents can be added.
     */
    var _newIncidentUrl = null;

    /**
     * Called to initialize the attachment forms, including adding new and deleting existing forms.
    */
    function _initAttachmentForms() {
        // icon to add new attachment forms
        var elem = $("#newattachment");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "attachments", /* formPrefix */
                "#emptyattachment", /* emptySelector */
                _initAttachmentForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing attachment forms
        $(".attachmentform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initAttachmentForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the incident forms, including adding new and deleting existing forms.
    */
    function _initIncidentForms() {
        // icon to add new incident forms
        var elem = $("#newincident");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "incidents", /* formPrefix */
                "#emptyincident", /* emptySelector */
                _initIncidentForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing incident forms
        $(".incidentform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initIncidentForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the identifier forms, including adding new and deleting existing forms.
    */
    function _initIdentifierForms() {
        // icon to add new identifier forms
        var elem = $("#newidentifier");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "identifiers", /* formPrefix */
                "#emptyidentifier", /* emptySelector */
                _initIdentifierForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing identifier forms
        $(".identifierform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initIdentifierForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the content person forms, including adding new and deleting existing forms.
    */
    function _initContentPersonForms() {
        // icon to add new content person forms
        var elem = $("#newperson");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "persons", /* formPrefix */
                "#emptyperson", /* emptySelector */
                _initContentPersonForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing content person forms
        $(".personform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initContentPersonForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the content case forms, including adding new and deleting existing forms.
    */
    function _initContentCaseForms() {
        // icon to add new case forms
        var elem = $("#newcase");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "cases", /* formPrefix */
                "#emptycase", /* emptySelector */
                _initContentCaseForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing content case forms
        $(".caseform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initContentCaseForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Marks an attachment form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of attachment form to delete.
    */
    function _delAttachmentForm(id) {
        Fdp.Common.delInlineForm(
            "attachments", /* formPrefix */
            id, /* id */
            ".attachmentform" /* parentSelector */
        );
    };

    /**
     * Marks an incident form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of incident form to delete.
    */
    function _delIncidentForm(id) {
        Fdp.Common.delInlineForm(
            "incidents", /* formPrefix */
            id, /* id */
            ".incidentform" /* parentSelector */
        );
    };

    /**
     * Marks an identifier form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of identifier form to delete.
    */
    function _delIdentifierForm(id) {
        Fdp.Common.delInlineForm(
            "identifiers", /* formPrefix */
            id, /* id */
            ".identifierform" /* parentSelector */
        );
    };

    /**
     * Marks a content person form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of content person form to delete.
    */
    function _delContentPersonForm(id) {
        Fdp.Common.delInlineForm(
            "persons", /* formPrefix */
            id, /* id */
            ".personform" /* parentSelector */
        );
    };

    /**
     * Marks a content case form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of content case form to delete.
    */
    function _delContentCaseForm(id) {
        Fdp.Common.delInlineForm(
            "cases", /* formPrefix */
            id, /* id */
            ".caseform" /* parentSelector */
        );
    };

    /**
     * Initializes an attachment form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing attachment form. Must be wrapped in JQuery object.
    */
    function _initAttachmentForm(formContainer) {
        var delBtn = formContainer.find(".delattachment");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delAttachmentForm(
                id /* id */
            );
        });
        // attachment autocomplete search
        var attachmentSearchInput = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".attachmentname" /* selector */);
        var attachmentIdInput = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".attachment" /* selector */);
        // attachment searching with autocomplete
        Fdp.Common.initAutocomplete(
            attachmentSearchInput, /* searchInputElem */
            attachmentIdInput, /* idInputElem */
            _getAttachmentsUrl, /* ajaxUrl */
            "attachmentac" /* extraCssClass */
        );
        // ability to add new attachments through wizard
        var emptyAttLink = $("#emptynewattachment").children().clone();
        attachmentSearchInput.after(emptyAttLink);
        var newAttBtn = formContainer.find(_newAttSelector);
        var uniqueId = "newattachment";
        newAttBtn.on("click", function (e) {
            if (!w[Fdp.Common.windowFuncs]) { w[Fdp.Common.windowFuncs] = {}; }
            // close all windows opened previously through new attachment button
            Fdp.Common.closePopups(uniqueId /* uniqueId */);
            w[Fdp.Common.windowFuncs][uniqueId] = function (attachmentId, attachmentName) {
                Fdp.Common.closePopups(uniqueId /* uniqueId */);
                attachmentSearchInput.val(attachmentName);
                attachmentIdInput.val(attachmentId);
                Fdp.Common.showAutocompleteOk(attachmentSearchInput /* searchInputElem */);
            };
            Fdp.Common.openPopup(
                _newAttachmentUrl, /* url */
                uniqueId, /* uniqueId */
                true /* makeAbsolute */
            );
            e.preventDefault();
        });
        // copy hidden errors to the corresponding visible input
        Fdp.Common.copyErrorsFromInput(
            attachmentIdInput, /* fromInput */
            attachmentSearchInput /* toInput */
        );
    };

    /**
     * Initializes an incident form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing incident form. Must be wrapped in JQuery object.
    */
    function _initIncidentForm(formContainer) {
        var delBtn = formContainer.find(".delincident");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delIncidentForm(
                id /* id */
            );
        });
        // incident autocomplete search
        var incidentSearchInput = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".incidentname" /* selector */);
        var incidentIdInput = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".incident" /* selector */);
        // incident searching with autocomplete
        Fdp.Common.initAutocomplete(
            incidentSearchInput, /* searchInputElem */
            incidentIdInput, /* idInputElem */
            _getIncidentsUrl, /* ajaxUrl */
            "incidentac" /* extraCssClass */
        );
        // ability to add new incidents through wizard
        var emptyIncLink = $("#emptynewincident").children().clone();
        incidentSearchInput.after(emptyIncLink);
        var newIncBtn = formContainer.find(_newIncSelector);
        var uniqueId = "newincident";
        newIncBtn.on("click", function (e) {
            // build extra GET parameters from content and content case fields that may be
            // used to define initial values for incident
            var startMonth = $("#id_cases-0-case_opened_0").val();
            var startDay = $("#id_cases-0-case_opened_1").val();
            var startYear = $("#id_cases-0-case_opened_2").val();
            var endMonth = $("#id_cases-0-case_closed_0").val();
            var endDay = $("#id_cases-0-case_closed_1").val();
            var endYear = $("#id_cases-0-case_closed_2").val();
            var forHostOnly = ($("#id_for_host_only").is(":checked") === true);
            var forAdminOnly = ($("#id_for_admin_only").is(":checked") === true);
            var forOrganizations = $("#id_fdp_organizations").val() || [];
            var extraGetParmaters = Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.startYearGetParam, /* paramName */ startYear /* paramValue */
            ) + Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.startMonthGetParam, /* paramName */ startMonth /* paramValue */
            ) + Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.startDayGetParam, /* paramName */ startDay /* paramValue */
            ) + Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.endYearGetParam, /* paramName */ endYear /* paramValue */
            ) + Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.endMonthGetParam, /* paramName */ endMonth /* paramValue */
            ) + Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.endDayGetParam, /* paramName */ endDay /* paramValue */
            ) + Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.hostOnlyGetParam, /* paramName */ forHostOnly /* paramValue */
            ) + Fdp.Common.getQueryStringParamNameAndValue(
                Fdp.Common.adminOnlyGetParam, /* paramName */ forAdminOnly /* paramValue */
            );
            for (var i=0; i<forOrganizations.length; i++) {
                extraGetParmaters += Fdp.Common.getQueryStringParamNameAndValue(
                    Fdp.Common.organizationsGetParam, /* paramName */ forOrganizations[i] /* paramValue */
                );
            }
            if (!w[Fdp.Common.windowFuncs]) { w[Fdp.Common.windowFuncs] = {}; }
            // close all windows opened previously through new incident button
            Fdp.Common.closePopups(uniqueId /* uniqueId */);
            w[Fdp.Common.windowFuncs][uniqueId] = function (incidentId, incidentName) {
                Fdp.Common.closePopups(uniqueId /* uniqueId */);
                incidentSearchInput.val(incidentName);
                incidentIdInput.val(incidentId);
                Fdp.Common.showAutocompleteOk(incidentSearchInput /* searchInputElem */);
            };
            Fdp.Common.openPopup(
                _newIncidentUrl + extraGetParmaters, /* url */
                uniqueId, /* uniqueId */
                true /* makeAbsolute */
            );
            e.preventDefault();
        });
        // copy hidden errors to the corresponding visible input
        Fdp.Common.copyErrorsFromInput(
            incidentIdInput, /* fromInput */
            incidentSearchInput /* toInput */
        );
    };

    /**
     * Initializes an identifier form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing identifier form. Must be wrapped in JQuery object.
    */
    function _initIdentifierForm(formContainer) {
        var delBtn = formContainer.find(".delidentifier");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delIdentifierForm(
                id /* id */
            );
        });

        // initialize multiple select element
        Fdp.Common.initPassiveSelect2ElemsInContainer(
            ".multiselect", /* selector */
            formContainer /* container */
        );

    };

    /**
     * Initializes a content person form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing content person form. Must be wrapped in JQuery object.
    */
    function _initContentPersonForm(formContainer) {
        console.log(formContainer)
        var delBtn = formContainer.find(".delperson");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delContentPersonForm(
                id /* id */
            );
        });
        var personSearchInput = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".personname" /* selector */);
        var personIdInput = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".person" /* selector */);
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
     * Initializes a content case form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing content case form. Must be wrapped in JQuery object.
    */
    function _initContentCaseForm(formContainer) {
        var delBtn = formContainer.find(".delcase");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delContentCaseForm(id /* id */);
        });
        // initialize newly added date pickers
        _initDatePickers(".caseform" /* containerSelector */);
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
     * Initializes interactivity for interface elements for adding and editing content through the data management tool. Should be called when DOM is ready.
     * @param {boolean} isEditing - True if content already exists, and we are editing it, false otherwise.
     * @param {string} getPersonsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of persons.
     * @param {string} getAttachmentsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of attachments.
     * @param {string} getIncidentsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of incidents.
     * @param {string} newAttachmentUrl - Relative URL through which new attachments can be added.
     * @param {string} newIncidentUrl - Relative URL through which new incidents can be added.
     */
	changingContentDef.init = function (
	    isEditing, getPersonsUrl, getAttachmentsUrl, getIncidentsUrl, newAttachmentUrl, newIncidentUrl
	) {

        _isEditing = isEditing;
        _getPersonsUrl = getPersonsUrl;
        _getAttachmentsUrl = getAttachmentsUrl;
        _getIncidentsUrl = getIncidentsUrl;
        _newAttachmentUrl = newAttachmentUrl;
        _newIncidentUrl = newIncidentUrl;

        // disable enter key for page
        Fdp.Common.disableEnterKey();

        // initialize adding new and removing existing identifiers
        _initIdentifierForms();

        // initialize adding new and removing existing attachments
        _initAttachmentForms();

        // initialize adding new and removing existing content case
        _initContentCaseForms();

        // initialize adding new and removing existing incidents
        _initIncidentForms();

        // initialize adding new and removing existing content persons
        _initContentPersonForms();

        // initialize date pickers
        _initDatePickers(null /* containerSelector */);

        // initialize multiple select elements
        Fdp.Common.initPassiveSelect2Elems("#id_fdp_organizations" /* selector */);

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

	fdpDef.ChangingContent = changingContentDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
