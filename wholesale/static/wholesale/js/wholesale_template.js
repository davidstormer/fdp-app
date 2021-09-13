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
     * Array of selected models.
     */
    let _selectedModels = [];

    /**
     * Array of models related to the selected models.
     */
    let _relatedModels = [];

    /**
     * Object representing the relatedness between models with each attribute as a model name and the corresponding value a list of related models.
     */
    let _modelRelations = null;

    /**
     * Initializes interactivity for interface elements for generating templates for the wholesale import tool. Should be called when DOM is ready.
     * @param {Object} modelRelations - Object representing the relatedness between models.
     */
	wholesaleTemplateDef.init = function (modelRelations) {

        _modelRelations = modelRelations;

        let modelsSelector = "#id_models";

        // initialize multiple select elements
        Fdp.Common.initSelect2Elem(
            modelsSelector, /* select2Selector */
            {
                /**
                 * Formats each item appearing the dropdown list for the Select2 package.
                 * @param {Object} result - Object representing current item to format.
                 * @returns {Object} Formatted item.
                 */
                templateResult: function (result) {
                    let id = result.id;
                    let span = $("<span />", { });
                    span.text(result.text);
                    // this model is selected OR it is a model related to a selected model
                    if ((_selectedModels.includes(id) === true) || (_relatedModels.includes(id) === true)) {
                        let i = $("<i />", {class: "r fas fa-bezier-curve"});
                        i.appendTo(span);
                    }
                    return span;
                }
            } /* select2Options */
        );
        // listen to changes in models and updated "selected list" and "related list"
        $(modelsSelector).on("change", function (e) {
            let selectedModels = $(modelsSelector).val();
            _selectedModels = selectedModels;
            _relatedModels = [];
            let lenS = selectedModels.length;
            // cycle through selected models
            for (let i=0; i<lenS; i++) {
                let relatedModels = _modelRelations[selectedModels[i]];
                let lenR = relatedModels.length;
                // cycle through models related to current selection
                for (let j=0; j<lenR; j++) {
                    _relatedModels.push(relatedModels[j]);
                }
            }
        });

	};

	fdpDef.WholesaleTemplate = wholesaleTemplateDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
