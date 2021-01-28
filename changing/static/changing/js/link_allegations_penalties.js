/**
 * @file Functionality for linking allegations and penalties to content through the data management tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires jqueryui
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingAllegationsPenaltiesDef = {};

    /**
     * JQuery selector string to retrieve a containing element for allegations for a particular content-person.
     */
    var _allegationContainerSelector = "div.cpa";

    /**
     * JQuery selector string to retrieve a containing element for penalties for a particular content-person.
     */
    var _penaltyContainerSelector = "div.cpp";

    /**
     * Called to initialize the content person allegation forms, including adding new and deleting existing forms.
    */
    function _initContentPersonAllegationForms() {
        $(_allegationContainerSelector).each(function (i, elem) {
            var contentPersonContainer = $(elem);
            var contentPersonId = contentPersonContainer.data("id");

            // icon to add new allegation for this particular content person
            var newBtn = $("#newallegation" + contentPersonId);
            newBtn.on("click", function () {
                Fdp.Common.addInlineForm(
                    "allegations", /* formPrefix */
                    "#emptyallegation" + contentPersonId, /* emptySelector */
                    _initContentPersonAllegationForm, /* onAddFunc */
                    "<div />" /* newContSelector */
                );
            });

            // icons to remove existing allegations for this particular content person
            contentPersonContainer.find(".allegationform").not(".emptyform").each(function (j, element) {
                var formContainer = $(element);
                _initContentPersonAllegationForm(formContainer /* formContainer */);
                Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
            });
        });  // $("div.cpa).each(function (i, elem) {});
    };

    /**
     * Called to initialize the content person penalty forms, including adding new and deleting existing forms.
    */
    function _initContentPersonPenaltyForms() {
        $(_penaltyContainerSelector).each(function (i, elem) {
            var contentPersonContainer = $(elem);
            var contentPersonId = contentPersonContainer.data("id");

            // icon to add new penalty for this particular content person
            var newBtn = $("#newpenalty" + contentPersonId);
            newBtn.on("click", function () {
                Fdp.Common.addInlineForm(
                    "penalties", /* formPrefix */
                    "#emptypenalty" + contentPersonId, /* emptySelector */
                    _initContentPersonPenaltyForm, /* onAddFunc */
                    "<div />" /* newContSelector */
                );
            });

            // icons to remove existing penalties for this particular content person
            contentPersonContainer.find(".penaltyform").not(".emptyform").each(function (j, element) {
                var formContainer = $(element);
                _initContentPersonPenaltyForm(formContainer /* formContainer */);
                Fdp.Common.hideFormIfDeleted(formContainer /* containerToHide */);
            });
        });  // $("div.cpp).each(function (i, elem) {});
    };

    /**
     * Marks a content person allegation form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of content person allegation form to delete.
    */
    function _delContentPersonAllegationForm(id) {
        Fdp.Common.delInlineForm(
            "allegations", /* formPrefix */
            id, /* id */
            ".allegationform" /* parentSelector */
        );
    };

    /**
     * Marks a content person penalty form for deletion, and hides its corresponding HTML elements.
     * @param {number} id - Id of content person penalty form to delete.
    */
    function _delContentPersonPenaltyForm(id) {
        Fdp.Common.delInlineForm(
            "penalties", /* formPrefix */
            id, /* id */
            ".penaltyform" /* parentSelector */
        );
    };

    /**
     * Initializes a content person allegation form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing content person allegation form. Must be wrapped in JQuery object.
    */
    function _initContentPersonAllegationForm(formContainer) {
        var delBtn = formContainer.find(".delallegation");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delContentPersonAllegationForm(
                id /* id */
            );
        });

        // if the link to the content person is not already set, then set it
        var contentPersonInput = formContainer.find(".foreignkey");
        if (!contentPersonInput.val()) {
            // find main container for all allegations for this particular content person
            var contentPersonContainer = contentPersonInput.closest(_allegationContainerSelector);
            var contentPersonId = contentPersonContainer.data("id");
            contentPersonInput.val(contentPersonId);
        }
    };

    /**
     * Initializes a content person penalty form, including adding an event handler to the corresponding delete icon.
     * @param {Object} formContainer - Element containing content person penalty form. Must be wrapped in JQuery object.
    */
    function _initContentPersonPenaltyForm(formContainer) {
        var delBtn = formContainer.find(".delpenalty");
        var id = delBtn.data("id");
        delBtn.one("click", function () {
            _delContentPersonPenaltyForm(
                id /* id */
            );
        });

        // if the link to the content person is not already set, then set it
        var contentPersonInput = formContainer.find(".foreignkey");
        if (!contentPersonInput.val()) {
            // find main container for all penalties for this particular content person
            var contentPersonContainer = contentPersonInput.closest(_penaltyContainerSelector);
            var contentPersonId = contentPersonContainer.data("id");
            contentPersonInput.val(contentPersonId);
        }

        // initialize date pickers
        Fdp.Common.initDatePickers(
            /**
             * Function called when a date is selected through the JQuery UI Datepicker.
             * @param {string} selectedDate - Date was selected in the Datepicker plugin. Will be in the format of "mm/dd/yyyy".
             * @param {Object} datepickerInstance - Instance of Datepicker through which date was selected.
            */
            function (selectedDate, datepickerInstance) {
                var span = $(datepickerInstance.input);
                var inputs = span.siblings("input");
                var input = inputs.first();
                input.val(selectedDate);
            }, /* onDateSelectFunc */
            ".penaltyform" /* containerSelector */
        );

    };

    /**
     * Initializes interactivity for interface elements for linking allegations and penalties to content through the data management tool. Should be called when DOM is ready.
     */
	changingAllegationsPenaltiesDef.init = function () {

        // disable enter key for page
        Fdp.Common.disableEnterKey();

        // initialize multiple select elements and then disable them
        Fdp.Common.initPassiveSelect2Elems(".multiselect" /* selector */);
        Fdp.Common.disableSelect2Elem(".multiselect" /* selector */);

        // initialize adding new and removing existing content person allegations
        _initContentPersonAllegationForms();

        // initialize adding new and removing existing content person penalties
        _initContentPersonPenaltyForms();

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

	fdpDef.ChangingAllegationsPenalties = changingAllegationsPenaltiesDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
