/**
 * @file Functionality for a user reviewing and then agreeing to an end-user license agreement (EULA).
 * @requires Fdp.Common
 * @requires jquery
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

    var eulaRequiredDef = {};

    /**
     * Initializes interactivity for interface elements for a user reviewing and then agreeing to an end-user license agreement (EULA). Should be called when DOM is ready.
     */
	eulaRequiredDef.init = function () {

        let agreedSelector = "#agreed";

        $(agreedSelector).one("click", function () {
            $(agreedSelector).remove();
            $("#agreetoeula").trigger("submit");
        });

	};

	fdpDef.EulaRequired = eulaRequiredDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
