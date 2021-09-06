/**
 * @file Functionality for generating templates for the wholesale import tool.
 * @requires Fdp.Common
 * @requires jquery
 * @requires select2
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var wholesaleTemplateDef = {};

    /**
     * Initializes interactivity for interface elements for generating templates for the wholesale import tool. Should be called when DOM is ready.
     */
	wholesaleTemplateDef.init = function () {

        // initialize multiple select elements
        Fdp.Common.initPassiveSelect2Elems(".multiselect" /* selector */);

	};

	fdpDef.WholesaleTemplate = wholesaleTemplateDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
