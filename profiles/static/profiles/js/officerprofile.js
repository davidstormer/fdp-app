/**
 * @file Functionality for searching and viewing an officer profile.
 * @requires Fdp.Common
 * @requires jquery
 * @requires slick
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var officerProfileDef = {};

    /**
     * Initializes interactivity for interface elements for the officer profile. Should be called when DOM is ready.
     */
	officerProfileDef.init = function () {
        var photos = $(".photos");
        // init photo carousel
        photos.slick({
            dots: true,
            centerMode: true,
            variableWidth: true,
            centerPadding: "100px"
        });
        // init expandable / collapsible sections
        var collapsibleButtons = "button.collapsible";
        $(collapsibleButtons).each(function (i, elem) {
            var button = $(elem);
            var div = button.next("div.collapsible");
            var onStart = function () { photos.slick('setPosition'); };
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

	fdpDef.OfficerProfile = officerProfileDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
