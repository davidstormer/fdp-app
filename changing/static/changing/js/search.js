/**
 * @file Functionality for searching for existing or adding new content, incidents, personnel and groupings through the data management tools.
 * @requires Fdp.Common
 * @requires jquery
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var changingSearchDef = {};

    /**
     * Initializes interactivity for interface elements for searching or adding new content, incidents, personnel and groupings through the data management tools. Should be called when DOM is ready.
     */
	changingSearchDef.init = function () {

	};

	fdpDef.ChangingSearch = changingSearchDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
