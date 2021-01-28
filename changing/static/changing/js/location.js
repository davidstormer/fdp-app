/**
 * @file Functionality for adding and editing locations through the data management tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires jqueryui
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingLocationDef = {};

    /**
     * Initializes interactivity for interface elements for adding and editing locations through the data management tool. Should be called when DOM is ready.
     * @param {boolean} isEditing - True if location already exists, and we are editing it, false otherwise.
     * @param {string} popupKey - Queryset GET parameter used to indicate whether location form is being rendered as a popup.
     * @param {string} popupValue - Queryset GET parameter value used to indicate whether location form is being rendered as a popup.
     * @param {string} popupIdKey - Queryset GET parameter used to indicate the unique identifier for the form that is being rendered as a popup.
     * @param {string} popupField - Name of popup field that will be used to contain the unique identifier for the form when it is rendered as a popup.
     */
	changingLocationDef.init = function (isEditing, popupKey, popupValue, popupIdKey, popupField) {

        // initialize multiple select elements
        Fdp.Common.initPassiveSelect2Elems(".multiselect" /* selector */);

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

	fdpDef.ChangingLocation = changingLocationDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
