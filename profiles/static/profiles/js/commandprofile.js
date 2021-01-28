/**
 * @file Functionality for searching and viewing a command profile.
 * @requires Fdp.Common
 * @requires jquery
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var commandProfileDef = {};

    /**
     * Initializes interactivity for interface elements for the command profile. Should be called when DOM is ready.
     */
	commandProfileDef.init = function () {
        // init expandable / collapsible sections
        var collapsibleButtons = "button.collapsible";
        $(collapsibleButtons).each(function (i, elem) {
            var button = $(elem);
            var div = button.next("div.collapsible");
            var onStart = function () { };
            var onComplete = null;
            Fdp.Common.initCollapsible(
                button, /* button */
                div, /* div */
                onStart, /* onStart */
                onComplete /* onComplete */
            );
        });
        // expand all button is clicked
        $("#i_expandall").on("click", function () {
            $(collapsibleButtons).each(function (i, elem) {
                var button = $(elem);
                if (button.hasClass("expanded") === false) {
                    button.trigger("click");
                }
            });
        });
        // collapse all button is clicked
        $("#i_collapseall").on("click", function () {
            $(collapsibleButtons).each(function (i, elem) {
                var button = $(elem);
                if (button.hasClass("expanded") === true) {
                    button.trigger("click");
                }
            });
        });
	};

	fdpDef.CommandProfile = commandProfileDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
