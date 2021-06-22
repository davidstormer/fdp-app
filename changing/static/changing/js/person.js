/**
 * @file Functionality for adding and editing persons through the data management tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires jqueryui
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingPersonDef = {};

    /**
     * A dummy value for an ID attribute that matches NO elements in the HTML. Used as a placeholder parameter for getConfigureFormFunc(...).
     */
    var _ignoredId = "ignoredXYZ";

    /**
	 * True when an existing person is being edited, false when a new person is being created. Set when page is initialized.
	 */
	var _isEditing = false;

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of groupings.
	 */
	var _getGroupingsUrl = null;

    /**
	 * URL to which asynchronous requests are sent to retrieve a filtered list of persons.
	 */
	var _getPersonsUrl = null;

    /**
	 * Retrieves the Checkbox element used to specify whether the person belongs to law enforcement or not.
	 * @returns {Object} Checkbox element used to specify whether the person belongs to law enforcement or not. Will be wrapped in JQuery object.
	 */
	var _getIsLawEnforcementCheckbox = function () { return $("#id_is_law_enforcement"); };

    /**
	 * Retrieves the container element in which the birth date range start field exists.
	 * @returns {Object} Container element for birth date range start field. Will be wrapped in JQuery object.
	 */
    var _getBirthDateRangeStartContainer = function () { return $("#f_id_birth_date_range_start"); };

    /**
	 * Retrieves the container element in which the birth date range end field exists.
	 * @returns {Object} Container element for birth date range end field. Will be wrapped in JQuery object.
	 */
    var _getBirthDateRangeEndContainer = function () { return $("#f_id_birth_date_range_end"); };

    /**
	 * Retrieves the container element in which the single birth date field exists.
	 * @returns {Object} Container element for single birth date field. Will be wrapped in JQuery object.
	 */
    var _getBirthDateContainer = function () { return $("#f_id_known_birth_date"); };

    /**
	 * Retrieves the birth date range start field.
	 * @returns {Object} Birth date range start field. Will be wrapped in JQuery object.
	 */
    var _getBirthDateRangeStartInput = function () { return (_getBirthDateRangeStartContainer()).find("input"); };

    /**
	 * Retrieves the birth date range end field.
	 * @returns {Object} Birth date range end field. Will be wrapped in JQuery object.
	 */
    var _getBirthDateRangeEndInput = function () { return (_getBirthDateRangeEndContainer()).find("input"); };

    /**
	 * Retrieves the single birth date field.
	 * @returns {Object} Single birth date field. Will be wrapped in JQuery object.
	 */
    var _getBirthDateInput = function () { return (_getBirthDateContainer()).find("input"); };

    /**
	 * Sets the classes for labels corresponding to form fields.
	 */
    function _setLabelClasses() {
        // the grouping SELECT element for person groupings
        $("input.groupingname").each(function (i, elem) {
            var select = $(elem);
            var label = select.prev("label");
            label.addClass("grouping");
        });
        // the title SELECT element for person titles
        $("select.title").each(function (i, elem) {
            var select = $(elem);
            var label = select.prev("label");
            label.addClass("title");
        });
    };

    /**
	 * Called when any of the form templates are selected to be displayed.
	 */
    function _onCompleteForTemplate() {
        // container to remove still exists (this is the first time the template is rendered)
        var containerToDelete = $("#cust_personselectcont");
        if (containerToDelete.length > 0) {
            // hide container and then delete it
            Fdp.Common.fadeOut(
                containerToDelete, /* elemToFadeOut */
                function () { containerToDelete.remove(); } /* onCompleteFunc */
            );
        }
        var manualDisplayClass = ".manualdisplay"
        var isLawEnforcementCheckbox = _getIsLawEnforcementCheckbox();
        var isLawEnforcement = isLawEnforcementCheckbox.is(":checked");
        var cls = "";
        isLawEnforcementCheckbox.off("change");
        isLawEnforcementCheckbox.one("change", function () {
            var innerIsLawEnforcement = $(this).is(":checked");
            Fdp.Common.getConfigureFormFunc(
                innerIsLawEnforcement.toString(), /* selectedId */
                _ignoredId, /* fieldFieldName */
                _onCompleteForTemplate /* defaultOnComplete */
            )();
        });

        // law enforcement was selected
        if (isLawEnforcement === true) {
            cls = ".manualdisplaylaw";
        }
        // not law enforcement was selected
        else if (isLawEnforcement === false) {
            cls = ".manualdisplaynotlaw";
        }
        // hide all elements that are no form fields or inline forms, but were displayed for the previous selection
        Fdp.Common.fadeOut(
            $(manualDisplayClass + ":not(" + cls + ")"), /* elemToFadeOut */
            null /* onCompleteFunc */
        );

        // display all elements that are not form fields or inline forms
        Fdp.Common.fadeIn(
            $(manualDisplayClass + cls), /* elemToFadeIn */
            null /* onCompleteFunc */
        );
        // determines which birth date related fields to show / hide
        _showOrHideBirthDateFields();
    };

    /**
	 * Called to hide the birth date range.
	 * @param {function} onCompleteFunc - Function to call when birth date range is hidden.
	 */
    function _hideBirthDateRange(onCompleteFunc) {
        var startDateContainer = _getBirthDateRangeStartContainer();
        var endDateContainer = _getBirthDateRangeEndContainer();
        var startDateInput = _getBirthDateRangeStartInput();
        var endDateInput = _getBirthDateRangeEndInput();
        var toHideElems = startDateContainer.add(endDateContainer);
        startDateInput.val("");
        endDateInput.val("");
        Fdp.Common.fadeOut(
            toHideElems, /* elemToFadeOut */
            onCompleteFunc /* onCompleteFunc */
        );
    };

    /**
	 * Called to show the birth date range.
	 * @param {function} onCompleteFunc - Function to call when birth date range is shown.
	 */
    function _showBirthDateRange(onCompleteFunc) {
        var startDateContainer = _getBirthDateRangeStartContainer();
        var endDateContainer = _getBirthDateRangeEndContainer();
        var toShowElems = startDateContainer.add(endDateContainer);
        Fdp.Common.fadeIn(
            toShowElems, /* elemToFadeIn */
            onCompleteFunc /* onCompleteFunc */
        );
    };

    /**
	 * Called to hide the known birth date.
	 * @param {function} onCompleteFunc - Function to call when known birth date is hidden.
	 */
    function _hideKnownBirthDate(onCompleteFunc) {
        var dateContainer = _getBirthDateContainer();
        var dateInput = _getBirthDateInput();
        dateInput.val("");
        Fdp.Common.fadeOut(
            dateContainer, /* elemToFadeOut */
            onCompleteFunc /* onCompleteFunc */
        );
    };

    /**
	 * Called to show the known birth date.
	 * @param {function} onCompleteFunc - Function to call when known birth date is shown.
	 */
    function _showKnownBirthDate(onCompleteFunc) {
        var dateContainer = _getBirthDateContainer();
        Fdp.Common.fadeIn(
            dateContainer, /* elemToFadeIn */
            onCompleteFunc /* onCompleteFunc */
        );
    };

    /**
	 * Called when an exact birth date is known.
	 */
    function _exactBirthDateKnown() {
        _hideBirthDateRange(
            _showKnownBirthDate /* onCompleteFunc */
        );
    };

    /**
	 * Called when only a birth date range is known.
	 */
    function _onlyBirthDateRangeKnown() {
        _hideKnownBirthDate(
            _showBirthDateRange /* onCompleteFunc */
        );
    };

    /**
	 * Called to determine whether to show or hide birth date related fields.
	 */
    function _showOrHideBirthDateFields() {
        var knownBirthDateInput = _getBirthDateInput();
        var startBirthDateRangeInput = _getBirthDateRangeStartInput();
        var endBirthDateRangeInput = _getBirthDateRangeEndInput();

        // show the single known birth date field if there is a value for it, or if both birth date range fields are empty
        if (
                (knownBirthDateInput.val())
            ||
                (
                    (!startBirthDateRangeInput.val()) && (!endBirthDateRangeInput.val())
                )
            ) {
            _exactBirthDateKnown();
        }
        // there is no value for known birth date field, so show the birth date range
        else {
            _onlyBirthDateRangeKnown();
        }
    };

    /**
	 * Called to initialize birth date fields, converting from an exact birth date to a birth date range.
	 */
    function _initBirthDateFields() {
        $("span.splitdate").on("click", function () {
            _onlyBirthDateRangeKnown();
        });
        $("span.combinedate").on("click", function () {
            _exactBirthDateKnown();
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
     * Called to initialize the person grouping forms, including adding new and deleting existing forms.
    */
    function _initPersonGroupingForms() {
        // icon to add new person grouping forms
        var elem = $("#newpersongrouping");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "persongroupings", /* formPrefix */
                "#emptypersongrouping", /* emptySelector */
                _initPersonGroupingForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing person grouping forms
        $(".persongroupingform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonGroupingForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the person title forms, including adding new and deleting existing forms.
    */
    function _initPersonTitleForms() {
        // icon to add new title forms
        var elem = $("#newpersontitle");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "titles", /* formPrefix */
                "#emptypersontitle", /* emptySelector */
                _initPersonTitleForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing person title forms
        $(".persontitleform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonTitleForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the person payment forms, including adding new and deleting existing forms.
    */
    function _initPersonPaymentForms() {
        // icon to add new payment forms
        var elem = $("#newpersonpayment");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "payments", /* formPrefix */
                "#emptypersonpayment", /* emptySelector */
                _initPersonPaymentForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        var formSelector = ".personpaymentform";
        // icons to remove existing person title forms
        $(formSelector).not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonPaymentForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });

        // remove month, day, year labels
        $(formSelector).each(function (i, elem) {
            var formContainer = $(elem);
            formContainer.find("span.textmonth").remove();
            formContainer.find("span.textday, span.textyear").text("/");
        });
    };

    /**
     * Called to initialize the person alias forms, including adding new and deleting existing forms.
    */
    function _initPersonAliasForms() {
        // icon to add new alias forms
        var elem = $("#newpersonalias");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "aliases", /* formPrefix */
                "#emptypersonalias", /* emptySelector */
                _initPersonAliasForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing person alias forms
        $(".personaliasform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonAliasForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the person relationships forms, including adding new and deleting existing forms.
    */
    function _initPersonRelationshipForms() {
        // icon to add new relationship forms
        var elem = $("#newpersonrelationship");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "relationships", /* formPrefix */
                "#emptypersonrelationship", /* emptySelector */
                _initPersonRelationshipForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });
        // icons to remove existing person relationship forms
        $(".personrelationshipform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonRelationshipForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the person contact forms, including adding new and deleting existing forms.
    */
    function _initPersonContactForms() {
        // icon to add new contact forms
        var elem = $("#newpersoncontact");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "contacts", /* formPrefix */
                "#emptypersoncontact", /* emptySelector */
                _initPersonContactForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing person contact forms
        $(".personcontactform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonContactForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
    };

    /**
     * Called to initialize the person photo forms, including adding new and deleting existing forms.
    */
    function _initPersonPhotoForms() {
        // icon to add new photo forms
        var elem = $("#newpersonphoto");
        elem.on("click", function () {
            Fdp.Common.addInlineForm(
                "photos", /* formPrefix */
                "#emptypersonphoto", /* emptySelector */
                _initPersonPhotoForm, /* onAddFunc */
                "<div />" /* newContSelector */
            );
        });

        // icons to remove existing person photo forms
        $(".personphotoform").not(".emptyform").each(function (i, elem) {
            var formContainer = $(elem);
            _initPersonPhotoForm(
                formContainer /* formContainer */
            );

            Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
        });
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
     * Marks a person grouping form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person grouping form to delete.
    */
    function _delPersonGroupingForm(id) {
        Fdp.Common.delInlineForm(
            "persongroupings", /* formPrefix */
            id, /* id */
            ".persongroupingform" /* parentSelector */
        );
    };

    /**
     * Marks a person title form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person title form to delete.
    */
    function _delPersonTitleForm(id) {
        Fdp.Common.delInlineForm(
            "titles", /* formPrefix */
            id, /* id */
            ".persontitleform" /* parentSelector */
        );
    };

    /**
     * Marks a person payment form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person payment form to delete.
    */
    function _delPersonPaymentForm(id) {
        Fdp.Common.delInlineForm(
            "payments", /* formPrefix */
            id, /* id */
            ".personpaymentform" /* parentSelector */
        );
    };

    /**
     * Marks a person alias form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person alias form to delete.
    */
    function _delPersonAliasForm(id) {
        Fdp.Common.delInlineForm(
            "aliases", /* formPrefix */
            id, /* id */
            ".personaliasform" /* parentSelector */
        );
    };

    /**
     * Marks a person relationship form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person relationship form to delete.
    */
    function _delPersonRelationshipForm(id) {
        Fdp.Common.delInlineForm(
            "relationships", /* formPrefix */
            id, /* id */
            ".personrelationshipform" /* parentSelector */
        );
    };

    /**
     * Marks a person contact form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person contact form to delete.
    */
    function _delPersonContactForm(id) {
        Fdp.Common.delInlineForm(
            "contacts", /* formPrefix */
            id, /* id */
            ".personcontactform" /* parentSelector */
        );
    };

    /**
     * Marks a person photo form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of person photo form to delete.
    */
    function _delPersonPhotoForm(id) {
        Fdp.Common.delInlineForm(
            "photos", /* formPrefix */
            id, /* id */
            ".personphotoform" /* parentSelector */
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

        // initialize newly added date pickers
        _initDatePickers(".identifierform" /* containerSelector */);
    };

    /**
     * Initializes a person grouping form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person grouping form. Must be wrapped in JQuery object.
    */
    function _initPersonGroupingForm(formContainer) {
        var delBtn = formContainer.find(".delgrouping");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonGroupingForm(
                id /* id */
            );
        });
        // initialize newly added date pickers
        _initDatePickers(".persongroupingform" /* containerSelector */);
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
     * Initializes a person title form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person title form. Must be wrapped in JQuery object.
    */
    function _initPersonTitleForm(formContainer) {
        var delBtn = formContainer.find(".deltitle");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonTitleForm(
                id /* id */
            );
        });
        // initialize newly added date pickers
        _initDatePickers(".persontitleform" /* containerSelector */);
    };

    /**
     * Initializes a person payment form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person payment form. Must be wrapped in JQuery object.
    */
    function _initPersonPaymentForm(formContainer) {
        var delBtn = formContainer.find(".delpayment");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonPaymentForm(
                id /* id */
            );
        });
        // initialize newly added date pickers
        _initDatePickers(".personpaymentform" /* containerSelector */);
        // initialize counties
        var countySelect = formContainer.find(".dynamiccounty");
        countySelect.on("focusin", function () {
            var d = "done";
            if (!countySelect.data(d)) {
                countySelect.data(d, true);
                var selectedVal = countySelect.val();
                var allOptions = $("#allcounties > option").clone();
                countySelect.html(allOptions);
                countySelect.find('option[value="' + selectedVal + '"]').prop("selected", "selected");
            }
        });
    };

    /**
     * Initializes a person alias form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person alias form. Must be wrapped in JQuery object.
    */
    function _initPersonAliasForm(formContainer) {
        var delBtn = formContainer.find(".delalias");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonAliasForm(
                id /* id */
            );
        });
    };

    /**
     * Toggle the input fields for a person relationship between a subject and object perspective.
     * @param {Object} aInput - The input to be faded out. Must be wrapped in JQuery object.
     * @param {Object} bInput - The input to be faded in. Must be wrapped in JQuery object.
     * @param {Object} aIcon - The icon to be faded out. Must be wrapped in JQuery object.
     * @param {Object} bIcon - The icon to be faded in. Must be wrapped in JQuery object.
    */
    function _changePersonRelationshipOrder(aInput, bInput, aIcon, bIcon) {
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
     * Called to handle an icon click event switching from subject person relationship to object person relationship, or vice-versa.
     * @param {Object} aId - The input element that will contain the ID value selected by the user. Must be wrapped in JQuery object.
     * @param {Object} bId - The input element for the ID that will be empty (and faded out). Must be wrapped in JQuery object.
     * @param {Object} aName - The input element that will contain the string value selected by the user. Must be wrapped in JQuery object.
     * @param {Object} bName - The input element for the string that will empty (and faded out). Must be wrapped in JQuery object.
     * @param {Object} aIcon - The icon to be faded in. Must be wrapped in JQuery object.
     * @param {Object} bIcon - The icon to be faded out. Must be wrapped in JQuery object.
    */
    function _changePersonRelationshipFromIcon(aId, bId, aName, bName, aIcon, bIcon) {
        aId.val(bId.val());
        bId.val("");
        aName.val(bName.val());
        bName.val("");
        _changePersonRelationshipOrder(
            bName, /* aInput */
            aName, /* bInput */
            bIcon, /* aIcon */
            aIcon /* bIcon */
        );
    };

    /**
     * Initializes a person relationship form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person relationship form. Must be wrapped in JQuery object.
    */
    function _initPersonRelationshipForm(formContainer) {
        var delBtn = formContainer.find(".delrelationship");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonRelationshipForm(
                id /* id */
            );
        });
        // initialize newly added date pickers
        _initDatePickers(".personrelationshipform" /* containerSelector */);
        // initialize relationship
        var subjectId = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".subjectid" /* selector */);
        var objectId = Fdp.Common.getAutocompleteIdElem(formContainer /* formContainer */, ".objectid" /* selector */);
        var subjectName = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".subjectname" /* selector */);
        var objectName = Fdp.Common.getAutocompleteSearchElem(formContainer /* formContainer */, ".objectname" /* selector */);
        var subjectIcon = formContainer.find(".subjectrelicon");
        var objectIcon = formContainer.find(".objectrelicon");
        // subject person searching with autocomplete
        Fdp.Common.initAutocomplete(
            subjectName, /* searchInputElem */
            subjectId, /* idInputElem */
            _getPersonsUrl, /* ajaxUrl */
            "personac" /* extraCssClass */
        );
        // object person searching with autocomplete
        Fdp.Common.initAutocomplete(
            objectName, /* searchInputElem */
            objectId, /* idInputElem */
            _getPersonsUrl, /* ajaxUrl */
            "personac" /* extraCssClass */
        );
        // subject person defined
        if (subjectName.val()) {
            _changePersonRelationshipOrder(
                objectName, /* aInput */
                subjectName, /* bInput */
                objectIcon, /* aIcon */
                subjectIcon /* bIcon */
            );
        }
        // object person defined (or this a new relationship, so nothing is defined)
        else {
            _changePersonRelationshipOrder(
                subjectName, /* aInput */
                objectName, /* bInput */
                subjectIcon, /* aIcon */
                objectIcon /* bIcon */
            );
        }
        subjectIcon.on("click", function () {
            _changePersonRelationshipFromIcon(
                objectId, /* aId */
                subjectId, /* bId */
                objectName, /* aName */
                subjectName, /* bName */
                objectIcon, /* aIcon */
                subjectIcon /* bIcon */
            );
        });
        objectIcon.on("click", function () {
            _changePersonRelationshipFromIcon(
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
     * Initializes a person contact form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person contact form. Must be wrapped in JQuery object.
    */
    function _initPersonContactForm(formContainer) {
        var delBtn = formContainer.find(".delcontact");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonContactForm(
                id /* id */
            );
        });
    };

    /**
     * Initializes a person photo form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing person photo form. Must be wrapped in JQuery object.
    */
    function _initPersonPhotoForm(formContainer) {
        var delBtn = formContainer.find(".delphoto");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delPersonPhotoForm(
                id /* id */
            );
        });
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
     * Localized alternative labels for form fields.
     */
    changingPersonDef.Command = "";
    changingPersonDef.Commands = "";
    changingPersonDef.Organization = "";
    changingPersonDef.Organizations = "";
    changingPersonDef.Rank = "";
    changingPersonDef.Ranks = "";
    changingPersonDef.Title = "";
    changingPersonDef.Titles = "";

    /**
     * Initializes interactivity for interface elements for adding and editing person through the data management tool. Should be called when DOM is ready.
     * @param {boolean} isEditing - True if person already exists, and we are editing it, false otherwise.
     * @param {string} getGroupingsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of groupings.
     * @param {string} getPersonsUrl - URL to which asynchronous requests are sent to retrieve a filtered list of persons.
     */
	changingPersonDef.init = function (isEditing, getGroupingsUrl, getPersonsUrl) {

        _isEditing = isEditing;
        _getGroupingsUrl = getGroupingsUrl;
        _getPersonsUrl = getPersonsUrl;

        var isLawEnforcementCheckbox = _getIsLawEnforcementCheckbox();
        var lawEnforcementTemplateId = "1";
        var notLawEnforcementTemplateId = "2";
        var trueBool = true;
        var falseBool = false;

        // disable enter key for page
        Fdp.Common.disableEnterKey();

        // set classes for labels corresponding to form fields
        _setLabelClasses();

        // map law enforcement persons to law enforcement template
        Fdp.Common.formTemplateMap[trueBool.toString()] = lawEnforcementTemplateId;
        // map not law enforcement persons to not law enforcement template
        Fdp.Common.formTemplateMap[falseBool.toString()] = notLawEnforcementTemplateId;
        // fields to display for each template
        Fdp.Common.createFormTemplateFieldMap(
            lawEnforcementTemplateId, /* key */
            [
                "is_law_enforcement",
                "name",
                "traits",
                "for_admin_only",
                "for_host_only",
                "fdp_organizations"
            ], /* fields */
            [
                "identifierform",
                "persongroupingform",
                "persontitleform",
                "personpaymentform",
                "personaliasform",
                "personrelationshipform"
            ], /* inlineForms */
            _onCompleteForTemplate, /* onCompleteFunc */
            null, /* optionsDict */
            {
                "label.grouping": changingPersonDef.Command, /* labelText */
                "button.cmds": [changingPersonDef.Commands, false], /* [labelText, hasColon] */
                "button.tls": [changingPersonDef.Ranks, false], /* [labelText, hasColon] */
                "span.cmd": [String(changingPersonDef.Command).toLowerCase(), false], /* [labelText, hasColon] */
                "span.tle": [String(changingPersonDef.Rank).toLowerCase(), false], /* [labelText, hasColon] */
                "label.title": changingPersonDef.Rank /* labelText */
            } /* labelsDict */
        );
        Fdp.Common.createFormTemplateFieldMap(
            notLawEnforcementTemplateId, /* key */
            [
                "is_law_enforcement",
                "name",
                "for_admin_only",
                "for_host_only",
                "fdp_organizations"
            ], /* fields */
            [
                "identifierform",
                "persongroupingform",
                "persontitleform",
                "personaliasform",
                "personrelationshipform",
                "personcontactform"
            ], /* inlineForms */
            _onCompleteForTemplate, /* onCompleteFunc */
            null, /* optionsDict */
            {
                "label.grouping": changingPersonDef.Organization, /* labelText */
                "button.cmds": [changingPersonDef.Organizations, false] /* [labelText, hasColon] */,
                "button.tls": [changingPersonDef.Titles, false], /* [labelText, hasColon] */
                "span.cmd": [String(changingPersonDef.Organization).toLowerCase(), false], /* [labelText, hasColon] */
                "span.tle": [String(changingPersonDef.Title).toLowerCase(), false], /* [labelText, hasColon] */
                "label.title": changingPersonDef.Title /* labelText */
            } /* labelsDict */

        );

        // initializes the configurable form
        // changing the section in the top-level SELECT element that configures the form
        var firstSelect = $("#cust_personselect");
        firstSelect.one("change", function () {
            var innerIsLawEnforcement = (this.value == "true");
            isLawEnforcementCheckbox.prop("checked", innerIsLawEnforcement);
            Fdp.Common.getConfigureFormFunc(
                innerIsLawEnforcement.toString(), /* selectedId */
                _ignoredId, /* fieldFieldName */
                _onCompleteForTemplate /* defaultOnComplete */
            )();
        });

        // initialize adding new and removing existing identifiers
        _initIdentifierForms();

        // initialize adding new and removing existing person groupings
        _initPersonGroupingForms();

        // initialize adding new and removing existing person titles
        _initPersonTitleForms();

        // initialize adding new and removing existing person payment
        _initPersonPaymentForms();

        // initialize adding new and removing existing person alias
        _initPersonAliasForms();

        // initialize adding new and removing existing person relationship
        _initPersonRelationshipForms();

        // initialize adding new and removing existing person contact
        _initPersonContactForms();

        // initialize adding new and removing existing person photos
        _initPersonPhotoForms();

        // initialize date pickers
        _initDatePickers(null /* containerSelector */);

        // initialize multiple select elements
        Fdp.Common.initPassiveSelect2Elems(".multiselect" /* selector */);

        // initialize birth date related fields
        _initBirthDateFields();

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

        // We are editing an existing person
        if (_isEditing === true) {
            var isLawEnforcement = isLawEnforcementCheckbox.is(":checked");
            Fdp.Common.getConfigureFormFunc(
                isLawEnforcement.toString(), /* selectedId */
                _ignoredId, /* fieldFieldName */
                _onCompleteForTemplate /* defaultOnComplete */
            )();
        }

	};

	fdpDef.ChangingPerson = changingPersonDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
