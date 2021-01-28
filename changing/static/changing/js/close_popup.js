/**
 * @file Functionality for closing a popup window through the data management tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires jqueryui
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingClosePopupDef = {};

    /**
     * Initializes interface for closing the popup window opened through the data management tool. Should be called when DOM is ready.
     * @param {string} popupId - Unique identifier for the popup window. May be "TRUE" if no identifier was provided.
     * @param {number} pk - Primary key used to identify object selected or added in current popup window.
     * @param {string} strRep - String representation for the object selected or added in current popup window.
     */
	changingClosePopupDef.init = function (popupId, pk, strRep) {

        Fdp.Common.getPopupCallbackFunc(
            w, /* popupWindow */
            popupId, /* popupId */
            pk, /* pk */
            strRep /* strRep */
        )(null /* e */);

	};

	fdpDef.ChangingClosePopup = changingClosePopupDef ;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
