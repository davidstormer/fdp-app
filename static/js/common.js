/**
 * @file Functionality that is common through FDP and reused by various sections. JQuery UI only required for Datepicker-related or autocomplete functions.
 * @requires jquery
 * @requires jqueryui
 * @requires vex
 * @requires select2
 */
var Fdp = (function (fdpDef, $, w, d) {

    "use strict";

	var commonDef = {};

	/**
	 * Dictionary of all windows opened by the current parent window.
	 */
	var _openedWindows = {};

	/**
	 * Speed of CSS transitions in milliseconds, e.g. slide up, slide down, etc.
	 */
	var _speed = 400;

	/**
	 * ID of message dialogue container containing raw HTML.
	 */
	var _htmlDialogId = "showHtml";

	/**
	 * Prefix to prepend to the ID attribute of hidden elements that are created for client-side manipulation, such as filterable SELECT OPTIONs.
	 */
	var _hiddenElementPrefix = "fdphiddenElem";

	/**
	 * CSS class used to indicate that the autocomplete widget is in a valid state, e.g. when a user has selected one of its suggestions.
	 */
    var _okCssClass = "okac";

	/**
	 * CSS class used to indicate that the autocomplete widget is not in a valid state, e.g. when a user has changed the
	 * text in the search element, but has not yet selected a corresponding suggestion.
	 */
    var _notOkCssClass = "notokac";

    /**
     * Polyfill for .endsWith(...) for Internet Explorer.
     * @see {@link https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/endsWith#Polyfill|Mozilla}
     */
    if (!String.prototype.endsWith) {
        String.prototype.endsWith = function(search, this_len) {
            if (this_len === undefined || this_len > this.length) {
                this_len = this.length;
            }
            return this.substring(this_len - search.length, this_len) === search;
        };
    }

    /**
     * Checks whether a string represents a complete HTML page. This is a weak check, and only used for suspected Django error pages.
     * @param {string} html - String to check that may represent a complete HTML page.
     * @returns {boolean} True if string represents a complete HTML page, false otherwise.
     */
    function _isHtml(html) {
        // weak check only verifies that <html> element is exists somewhere in string
        return (html.indexOf("<html") !== -1);
    };

    /**
     * Builds a very basic complete HTML page.
     * @param {string} content - Content to place into the BODY element of the Html page.
     * @returns {string} A basic complete HTML page with content included.
     */
    function _buildHtml(content) {
        // escape HTML entities
        content = $("<div />").text(content).html();
        return "<!DOCTYPE html><html><head><title>" + commonDef.locError + "</title></head><body><pre>" + content + "</pre></body></html>";
    };

    /**
     * Retrieves a browser cookie by name.
     * @param {string} name - Name of cookie to retrieve.
     * @see {@link https://docs.djangoproject.com/en/2.1/ref/csrf/#acquiring-the-token-if-csrf-use-sessions-is-false|Django}
     * @returns {string} The contents of the cookie.
     */
    function _getCookie(name) {
        var cookieValue = null;
        if (d.cookie && d.cookie !== '') {
            var cookies = d.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = $.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    /**
     * Checks whether a method requires CSRF tokens to be sent during a request.
     * @param {string} method - Method to check.
     * @see {@link https://docs.djangoproject.com/en/2.1/ref/csrf/#setting-the-token-on-the-ajax-request|Django}
     * @returns {boolean} True if method does not require CSRF tokens, false otherwise.
     */
    function _csrfSafeMethod(method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    };

    /**
     * Retrieves the container to which hidden elements are created to manage client-side manipulations.
     * @returns {Object} HTML element containing hidden elements. Will be wrapped in JQuery object.
     */
    function _getHiddenElementContainer() {
        return $("body");
    };

    /**
     * Update a SELECT element by changing the available OPTIONs based on the template that is selected by the user.
     * @param {string} class_for_select - Class to uniquely identify the SELECT element to update, excluding any preceding dot (.).
     * @param {Array} arrayOfValues - Array of strings storing the names the values of OPTIONs that should be displayed for this template.
     */
	function _updateOptionsForFilterableSelect(class_for_select, arrayOfValues) {
        var container = _getHiddenElementContainer();
        var selectWithAllOptions = container.find("#" + _hiddenElementPrefix + class_for_select);
        var len = arrayOfValues.length;
        var selector = 'option[value=""]';
        // build selector for OPTIONs that should be displayed
        for (var i=0; i<len; i++) {
            selector += ', option[value="' + arrayOfValues[i] + '"]';
        }
        $("." + class_for_select).each(function (i, elem) {
            var selectToChange = $(elem);
            var selectedValue = selectToChange.val();
            // copy over all relevant OPTIONs
            selectToChange.empty();
            selectWithAllOptions.find(selector).clone().appendTo(selectToChange);
            // restore previous selection
            if (selectedValue) {
                selectToChange.val(selectedValue);
            }
        });
	};

    /**
     * Update a label's text.
     * @param {string} labelSelector - JQuery selector text used to identify the label.
     * @param {Object} labelObject - May be a string that is the text to use for the label. May also be a two element Array where the first element is the string that is the text to use for the label, and the second element is whether to append a colon or not, i.e. [labelText, hasColon].
     */
	function _updateLabelText(labelSelector, labelObject) {
        var labelText;
        var hasColon;
        // label object is a two element Array, i.e. [labelText, hasColon]
        if (Array.isArray(labelObject) === true) {
            labelText = labelObject[0];
            hasColon = labelObject[1];
        } else {
            labelText = labelObject;
            hasColon = true
        }
        $(labelSelector).text(labelText + ((hasColon === true) ? ":" : ""));
	};

    /**
     * Apply any default label text that are available, when no alternative labels are defined for a particular form tempalte.
     */
    function _applyDefaultLabelTexts() {
        // there are default labels to apply
        if (commonDef.noTemplate in commonDef.formTemplateAltLabelMap) {
            var labelsDict = commonDef.formTemplateAltLabelMap[commonDef.noTemplate];
            for (var labelSelector in labelsDict) {
                var labelObject = labelsDict[labelSelector];
                _updateLabelText(
                    labelSelector, /* labelSelector */
                    labelObject /* labelObject */
                );
            }
        } // end if there are default labels to apply
    };

    /**
     * Retrieves the function to asynchronously load records through the autocomplete.
     * @param {function} callbackFunc - Function to call when records have been loaded. Will be passed a single data parameter.
     * @param {string} ajaxUrl - Url through which records can be loaded asynchronously.
     * @returns {function} Function to asynchronously load records through the autocomplete.
     * @see {@link https://api.jqueryui.com/autocomplete/#option-source}
     */
    function _getAutocompleteLoadFunc(callbackFunc, ajaxUrl) {
        var url = ajaxUrl;
        /**
         * Asynchronously loads records through the autocomplete.
         * @param {string} searchTerm - Search term entered by user through which records will be filtered.
         */
        return function (searchTerm) {
            var ajaxData = {};
            var ajaxUrl = commonDef.makeAbsolute(url /* url */ );
            ajaxData[commonDef.jsonSearchCriteria] = searchTerm;
            commonDef.ajax(
                ajaxUrl, /* ajaxUrl */
                ajaxData, /* ajaxData */
                true, /* doStringify */
                function (data, type) {
                    callbackFunc(data /* data */ );
                }, /* onSuccess */
                false /* isForm */
            );
        };
    };

    /**
     * Retrieves the function to clear a hidden input element containing the ID value for a person, attachment, incident, etc. populated through autocomplete.
     * @param {Object} idInput - Hidden input storing ID value. Must be wrapped in JQuery object.
     * @returns {function} Clears a hidden input ID value.
     */
    function _getAutocompleteClearHiddenInputIdFunc(idInput) {

        /**
         * Clears a hidden input ID value for a person, attachment, incident, etc. populated through autocomplete.
         */
        return function () { idInput.val(""); };
    };

    /**
     * Retrieves the function to set the elements for an autocomplete, for instance when a suggestion is selected.
     * @param {Object} idInputElem - Input element in which hidden ID value is stored during autocomplete. Must be wrapped in JQuery object.
     * @param {Object} searchInputElem - Input element through which text searches are performed in autocomplete. Must be wrapped in JQuery object.
     * @returns {function} Function to set elements for an autocomplete.
     */
    function _getAutocompleteSetElements(idInputElem, searchInputElem) {

        /**
         * Sets elements for an autocomplete, for instance when a suggestion is selected.
         * @param {number} id - ID of selected record.
         * @param {string} name - String representation of selected record.
         */
        return function (id, name) {
            idInputElem.val(id);
            searchInputElem.val(name);
        };
    };

	/**
	 * Name of window property storing functions that can be called for this window from other popup windows.
	 */
	commonDef.windowFuncs = "fdpWinFuncs";

	/**
	 * Name of window property storing the unique ID for a popup window. Will be undefined for windows that are not popups.
	 */
	commonDef.windowUniqueId = "fdpWinUniId";

	/**
	 * Default status for VEX dialogs. This is ignored for now.
	 */
	commonDef.noStatus = 0;

	/**
	 * Number of characters that are required before JQueryUI Autocomplete is triggered.
	 */
	commonDef.autoCompleteChars = 2;

    /**
     * Default HTTP method to use for asynchronous (AJAX) requests.
     */
	commonDef.ajaxMethod = 'POST';

    /**
     * Default content type used to send JSON data to the server during asynchronous (AJAX) requests.
     */
	commonDef.ajaxContentType = 'application/json; charset=utf-8';

    /**
     * Default content type used to send form data to the server during asynchronous (AJAX) requests.
     */
	commonDef.formContentType = 'application/x-www-form-urlencoded; charset=UTF-8';

    /**
     * Asynchronous (AJAX) request returned HTML.
     */
	commonDef.ajaxHtmlReturned = 1;

    /**
     * Asynchronous (AJAX) request returned data.
     */
	commonDef.ajaxDataReturned = 2;

    /**
     * Default type of data expected from the server during asynchronous (AJAX) requests.
     */
	commonDef.ajaxDataType = 'json';

	/**
	 * Key representing when no customizable form template is defined. Used for the default values of alternative label text.
	 */
	commonDef.noTemplate = 0;

    /**
     * Mapping of IDs to a set of form templates. Used when customizing the form, its fields and labels, based on SELECT selections and other changes made on the client-side.
     */
    commonDef.formTemplateMap = {};

    /**
     * Mapping of form templates to a set of fields. Used when customizing the form, its fields and labels, based on SELECT selections and other changes made on the client-side.
     */
    commonDef.formTemplateFieldMap = {};

    /**
     * Mapping of form templates to a set of alternative labels for fields. Used when customizing the form, its fields and labels, based on SELECT selections and other changes made on the client-side.
     */
    commonDef.formTemplateAltLabelMap = {};

    /**
     * Mapping of form templates to a set of inline form class names. Used when customizing the form, its fields and labels, based on SELECT selections and other changes made on the client-side.
     */
    commonDef.formTemplateInlineFormMap = {};

    /**
     * Mapping of form templates to on complete functions to call. Used when customizing the form, its fields and labels, based on SELECT selections and other changes made on the client-side.
     */
    commonDef.formTemplateOnCompleteFuncMap = {};

    /**
     * Mapping of form templates to filtered SELECT OPTIONs. Used when showing/hiding OPTIONs in SELECT elements, based on SELECT selections and other changes made on the client-side.
     */
    commonDef.formTemplateSelectOptionMap = {};

    /**
     * Ensures that a URL starts with forward slash, to make it absolute.
     * @param {string} url - URL to check
     * @returns {string} Absolute URL that starts with the forward slash.
     */
    commonDef.makeAbsolute = function (url) {
        if (url.charAt(0) !== "/") {
            url = "/" + url;
        }
        return url;
    };

    /**
     * Ensures that the CSRF tokens are sent with each request using an unsafe method, and that loading animation is displayed appropriately.
     * @param {boolean} sendCsrf - True if CSRF token should be sent during asynchronous requests, false otherwise.
     * @see {@link https://docs.djangoproject.com/en/2.1/ref/csrf/#setting-the-token-on-the-ajax-request|Django}
     */
	commonDef.initAjax = function (sendCsrf) {
        if (sendCsrf === true) {
            // ensure CSRF tokens sent during requests
            $.ajaxSetup({
                beforeSend: function(xhr, settings) {
                    if (!_csrfSafeMethod(settings.type) && !this.crossDomain) {
                        xhr.setRequestHeader("X-CSRFToken", _getCookie('csrftoken'));
                    }
                }
            });
        }
        // ensure loading animation displayed
	    var img = $("<img />", {
	            class: "hidden",
	            id: "loading",
                src: "{{ STATIC_URL|escapejs }}" + "img/ajaxloading.gif",
                alt: commonDef.locLoading,
                title: commonDef.locLoading
	        });
	    $("body").append(img);
        $(d).ajaxStart(function () { img.fadeIn(_speed); }).ajaxStop(function () { img.fadeOut(_speed); });
	};

    /**
     * Initializes a collapsible section.
     * @param {Object} button - Button that is clicked to expand and collapse the section. Must be wrapped in JQuery object.
     * @param {Object} div - Section that is expanded and collapsed with a button click. Must be wrapped in JQuery object.
     * @param {function} onStart - Function to call when the expansion or collapse starts. May be null if ignored.
     * @param {function} onComplete - Function to call when the expansion or collapse completes. May be null if ignored.
     */
	commonDef.initCollapsible = function (button, div, onStart, onComplete) {
        button.on("click", function () {
            button.toggleClass("expanded");
            if (onComplete) { div.slideToggle(_speed, onComplete); }
            else { div.slideToggle(_speed); }
            if (onStart) { onStart(); }
        });
	};

    /**
     * Disables the Enter key on the page, except in textarea elements.
     */
	commonDef.disableEnterKey = function () {
        $(d).on("keydown", ":input:not(textarea)", function(event) {
            if (event.key == "Enter") {
                event.preventDefault();
            }
        });
	};

    /**
     * Fades an element into the display.
     * @param {Object} elemToFadeIn - Element to fade in. Must be wrapped in JQuery object.
     * @param {function} OnCompleteFunc - Function to call when the fade in is completed. May be null or undefined.
     */
	commonDef.fadeIn = function (elemToFadeIn, onCompleteFunc) {
        if (onCompleteFunc) {
            elemToFadeIn.fadeIn(_speed, onCompleteFunc);
        } else {
            elemToFadeIn.fadeIn(_speed);
        }
	};

    /**
     * Fades an element out of the display.
     * @param {Object} elemToFadeOut - Element to fade out. Must be wrapped in JQuery object.
     * @param {function} OnCompleteFunc - Function to call when the fade out is completed. May be null or undefined.
     */
	commonDef.fadeOut = function (elemToFadeOut, onCompleteFunc) {
        if (onCompleteFunc) {
            elemToFadeOut.fadeOut(_speed, onCompleteFunc);
        } else {
            elemToFadeOut.fadeOut(_speed);
        }
	};

    /**
     * Creates a mapping between a form template and its corresponding fields to display.
     * @param {string} key - Key that uniquely represents the form template. Must be a value found in commonDef.formTemplateMap[x].
     * @param {Array} fields - Array of strings storing the names of the fields to display for this particular form template.
     * @param {Array} inlineForms - Array of strings storing the class names of the inline forms to display for this particular form template.
     * @param {function} onCompleteFunc - Function to call when template is rendered, after forms and inline forms are displayed.
     * @param {Object} optionsDict - Dictionary where the keys are the unique class to identify the select, and the values are a list of option values to display.
     * @param {Object} labelsDict - Dictionary where the keys are the JQuery selector text used to identify the label, and the values are the alternative text for the label.
     */
    commonDef.createFormTemplateFieldMap = function (key, fields, inlineForms, onCompleteFunc, optionsDict, labelsDict) {
        if (fields) {
            commonDef.formTemplateFieldMap[key] = fields;
        }
        if (inlineForms) {
            commonDef.formTemplateInlineFormMap[key] = inlineForms;
        }
        if (onCompleteFunc) {
            commonDef.formTemplateOnCompleteFuncMap[key] = onCompleteFunc;
        }
        if (optionsDict) {
            commonDef.formTemplateSelectOptionMap[key] = optionsDict;
        }
        if (labelsDict) {
            commonDef.formTemplateAltLabelMap[key] = labelsDict;
        }
    };

    /**
     * Retrieves a function to call when a TOP-LEVEL SELECTION is made to configure a customizable form.
     * @param {number} selectedId - Id of value in TOP-LEVEL SELECTION.
     * @param {string} firstFieldName - Name of the first SELECT element whose selections can be used to configure the form.
     * @param {function} defaultOnComplete - Function to call when a TOP-LEVEL SELECTION is made to configure a customizable form, but there is no template defined for this value.
     * @returns {function} - Function to call when a TOP-LEVEL SELECTION is made to configure a customizable form.
     */
    commonDef.getConfigureFormFunc = function (selectedId, firstFieldName, defaultOnComplete) {
        /**
         * Function called when a TOP-LEVEL SELECTION is made to configure a customizable form.
         */
        return function () {
            var containerPrefix = "#f_id_";
            var neverShow = ".nevershow";
            var divFieldSelector = "div.form-row, td.form-row";
            var excludeSelector = neverShow + ", " + ".emptyform div";
            // all fields, excluding the first field, fields never to display, and fields in empty form templates
            var allFields = $(divFieldSelector).not(containerPrefix + firstFieldName + ", " + excludeSelector);
            // selected value has corresponding form template so display only the fields intended for template
            if (selectedId in commonDef.formTemplateMap) {
                var templateId = commonDef.formTemplateMap[selectedId];
                // hide all fields
                commonDef.fadeOut(
                    allFields, /* elemToFaceOut */
                    null /* onCompleteFunc */
                );
                // there are fields to display for this form template
                if (templateId in commonDef.formTemplateFieldMap) {
                    // fields to display for this form template
                    var fieldsToDisplay = commonDef.formTemplateFieldMap[templateId];
                    var len = fieldsToDisplay.length;
                    for(var i=0; i<len; i++) {
                        commonDef.fadeIn(
                            $(containerPrefix + fieldsToDisplay[i]), /* elemToFadeIn */
                            null /* onCompleteFunc */
                        );
                    }
                } // end if there are fields to display
                // there are inline forms to display for this form template
                if (templateId in commonDef.formTemplateInlineFormMap) {
                    // inline forms to display for this form template
                    var inlineFormsToDisplay = commonDef.formTemplateInlineFormMap[templateId];
                    var len = inlineFormsToDisplay.length;
                    for (var j=0; j<len; j++) {
                        var inlineForms = $("div." + inlineFormsToDisplay[j]);
                        inlineForms.each(function (i, elem) {
                            var inlineForm = $(elem);
                            var inlineFields = inlineForm.find(divFieldSelector).not(excludeSelector);
                            commonDef.fadeIn(
                                $(inlineFields), /* elemToFadeIn */
                                null /* onCompleteFunc */
                            );
                        });
                    }
                } // end if there are inline forms to display
                // there is a function to call for this form template
                if (templateId in commonDef.formTemplateOnCompleteFuncMap) {
                    var onCompleteFunc = commonDef.formTemplateOnCompleteFuncMap[templateId];
                    onCompleteFunc();
                } // end if there is a function to call
                // there are SELECT OPTIONs to filter for this form template
                if (templateId in commonDef.formTemplateSelectOptionMap) {
                    var optionsDict = commonDef.formTemplateSelectOptionMap[templateId];
                    for (var class_for_select in optionsDict) {
                        var listOfOptions = optionsDict[class_for_select];
                        _updateOptionsForFilterableSelect(
                            class_for_select, /* class_for_select */
                            listOfOptions /* arrayOfValues */
                        );
                    }
                } // end if there are filterable SELECT OPTIONs for this form template
                // there are alternative labels to apply for this form template
                if (templateId in commonDef.formTemplateAltLabelMap) {
                    var labelsDict = commonDef.formTemplateAltLabelMap[templateId];
                    for (var labelSelector in labelsDict) {
                        var labelObject = labelsDict[labelSelector];
                        _updateLabelText(
                            labelSelector, /* labelSelector */
                            labelObject /* labelObject */
                        );
                    }
                } // end if there are alternative labels too apply for this form template
                else { _applyDefaultLabelTexts(); }
            }
            // selected value does not have a corresponding form template defined so display all fields
            else {
                var allFieldsToShow = allFields;
                var hiddenContainer = _getHiddenElementContainer();
                // show all values for SELECT elements
                allFieldsToShow.find("select").each(function (i, elem){
                    var select = $(elem);
                    var uniqueClass = select.attr("class");
                    var hiddenSelect = hiddenContainer.find("#" + _hiddenElementPrefix + uniqueClass);
                    // only display all OPTIONs for SELECT element
                    // if it is a filterable select element (with corresponding hidden options)
                    if (hiddenSelect.length > 0) {
                        // store previously selected value
                        var selectedVal = select.val();
                        select.html(hiddenSelect.html());
                        // restore previously selected value
                        if (selectedVal) {
                            select.val(selectedVal);
                        }
                    }
                });
                // change label texts back to default
                _applyDefaultLabelTexts();
                // display all form fields, and all inline form fields
                commonDef.fadeIn(
                    allFieldsToShow, /* elemToFadeIn */
                    null /* onCompleteFunc */
                );
                // default on-complete function, e.g. to show save button
                defaultOnComplete();
            }
        };
    };

    /**
     * Scroll window to an HTML element.
     * @param {Object} element - Element to which to scroll. Must be wrapped in JQuery object.
     */
    commonDef.scrollToElement = function (element) {
        $([d.documentElement, d.body]).animate({scrollTop: element.offset().top}, 2000);
    };

    /**
     * Marks an inline form for deletion, and hides its corresponding HTML elements.
     * @param {string} formPrefix - Form prefix used by formset.
     * @param {number} id - Id of inline form to delete.
     * @param {string} parentSelector - JQuery selector text used to identify the closest ancestor, i.e. with closest(...) that is the containing element for the form.
    */
    commonDef.delInlineForm = function (formPrefix, id, parentSelector) {
        var deleteInput = $("#id_" + formPrefix + "-" + id + "-DELETE");
        var containerForm = deleteInput.closest(parentSelector);
        commonDef.fadeOut(
            containerForm, /* elemToFadeOut */
            null /* onCompleteFunc */
        );
        deleteInput.prop("checked", true);
    };

    /**
     * Add an inline form to a formset that is based on Django's formsets.
     * @param {string} formPrefix - Form prefix used by this formset.
     * @param {string} emptySelector - JQuery selector text to identify the element containing empty form template.
     * @param {function} onAddFunc - Function to call to add event listeners to the newly added form container.
     * @param {string} newContSelector - JQuery selector to create the new element containing the the form. Examples are: <div /> or <tr />.
     * @see {@link https://docs.djangoproject.com/en/2.1/topics/forms/formsets/|Django}
     */
    commonDef.addInlineForm = function (formPrefix, emptySelector, onAddFunc, newContSelector) {
        var totalFormsCounter = $("#id_" + formPrefix + "-TOTAL_FORMS");
        var emptyForm = $(emptySelector);
        var emptyFormContents = emptyForm.html();
        var numOfForms = parseInt(totalFormsCounter.val());
        var classList = emptyForm.attr("class").split(" ");

        // remove the emptyform class from the containing div
        var emptyFormPos = classList.indexOf("emptyform");
        if (emptyFormPos > -1) {
            classList.splice(emptyFormPos, 1);
        }
        // copy the empty form to a new container that is just above the empty form, and replace Django's generic form prefixes
        var toCont = $(newContSelector, {
            class: classList.join(' ')
        }).html(
            emptyFormContents.replace(/__prefix__/g, numOfForms)
        ).insertBefore(emptySelector);

        // if there are any event handlers to activate for the newly added container, then do so
        if (onAddFunc) {
            onAddFunc(toCont);
        }

        // increment number of forms counter
        totalFormsCounter.val(numOfForms + 1);

        // scroll to the newly added container
        commonDef.scrollToElement(
            toCont /* element */
        );

    };

    /**
     * Initializes JQuery UI Datepicker widgets.
     * @param {function} onDateSelectFunc - Function to call when a date is selected through the Datepicker.
       Will be passed the selected date and the instance of the datepicker through which it was selected.
     * @param {string} containerSelector - JQuery selector text used to identify the container in which the Datepickers should be initialized.
     Set to null if all Datepickers on page should be initialized.
    */
    commonDef.initDatePickers = function (onDateSelectFunc, containerSelector) {

        var clickNamespace = "click.datepicker";
        var className = "hasDatepicker";

        // Selector for HTML element to which Datepicker has been linked
        // (exclude Datepickers in empty form templates)
        // (exclude elements where Datepicker is already initialized)
        var datePickerSelector = "span.calendar:not(.emptyform span.calendar)";
        // Selector for icon that can be clicked to show Datepicker
        var iconSelector = "i.calendar:not(.emptyform i.calendar)";
        // if user specified a container selector, then add it to the datepicker selector
        if (containerSelector) {
            datePickerSelector = containerSelector + " " + datePickerSelector;
            iconSelector = containerSelector + " " + iconSelector;
        }
        // format of dates
        var dateFormat = "mm/dd/yy";
        // find all span elements to which the Datepicker plugin is linked
        $(datePickerSelector + ":not(span.calendar." + className + ")").each(function (i, elem) {
            var span = $(elem);
            // initialize the date picker
            span.datepicker({
                dateFormat: dateFormat,
                onSelect: function (dateText, inst) {
                    // update the corresponding year, month and day inputs when selecting a value
                    onDateSelectFunc(
                        dateText, /* selectedDate */
                        inst /* datepickerInstance */
                    );
                    // disable event handler listening for "click off" of calendar
                    $(d).off(clickNamespace);
                    span.datepicker().hide();
                },
                onClose: function (dateText, inst) {
                    // disable event handler listening for "click off" of calendar
                    $(d).off(clickNamespace);
                }
            });
            // close the datepickers initially, since they are linked to non-input elements
            span.datepicker().hide();
        });

        // find all icons which can be clicked to open the Datepicker plugin
        $(iconSelector).each(function (i, elem) {
            var i = $(elem);
            // when clicking on calendar icon, open the datepicker
            i.on("click", function (evt) {
                var span = i.prev(datePickerSelector);
                span.datepicker().show();
                // wait a bit, then add event handler listening for "click off" of calendar (to close it)
                setTimeout(
                    function () {
                        // when clicking on anything
                        $(d).on(clickNamespace, function (e) {
                            var clickedElement = $(e.target);
                            // if clicking on datepicker container
                            // or an element within the datepicker container
                            // or a dynamically added element associated with the datepicker, such as next and previous arrows
                            if (
                                (clickedElement.hasClass(className) === false)
                            &&  (clickedElement.closest("." + className).length === 0)
                            &&  (clickedElement.closest(".ui-datepicker-header").length === 0)
                            ) {
                                // disable event handler listening for "click off" of calendar
                                $(d).off(clickNamespace);
                                span.datepicker().hide();
                            }
                        }); // $(d).on(...);
                    }, // function in setTimeout
                    50
                ); // ends setTimeout
            }); // i.on("click", ...);
        }); // $(iconSelector).each(...);

    };

    /**
     * Retrieves a function that can be executed if an asynchronous (AJAX) call returns successfully.
     * Handled errors (exceptions) return successfully.
     * Returned JSON may contain data, HTML, a single primary key, or be empty.
     * @param {function} onSuccess - Function to call if async request was did not encounter an exception. May be passed parameters from the returned Json object.
     */
    commonDef.getOnSuccessAjaxFunc = function (onSuccess) {
        return function(json) {
            var parsedData = null;
            var isError = commonDef.jsonIsError;
            var isHtml = commonDef.jsonIsHtml;
            var isData = commonDef.jsonIsData;
            var isEmpty = commonDef.jsonIsEmpty;
            try {
                // see if JSON needs to be parsed
                parsedData = JSON.parse(json);
            } catch (err) {
                // was already valid parsed object
                parsedData = json;
            }
            // An exception was handled on the server level
            if ((parsedData.hasOwnProperty(isError))&&(parsedData[isError] === true)) {
                commonDef.showError(
                    commonDef.noStatus, /* status */
                    commonDef.locErrorTitle, /* title */
                    parsedData[commonDef.jsonError] /* message */
                );
            }
            // HTML generated during asynchronous request
            else if ((parsedData.hasOwnProperty(isHtml))&&(parsedData[isHtml] === true)) {
                onSuccess(
                    parsedData[commonDef.jsonHtml], /* data */
                    commonDef.ajaxHtmlReturned /* type */
                );
            }
            // Data added, changed or deleted during asynchronous request
            else if ((parsedData.hasOwnProperty(isData))&&(parsedData[isData] === true)) {
                onSuccess(
                    parsedData[commonDef.jsonData], /* data */
                    commonDef.ajaxDataReturned /* type */
                );
            }
            // Empty success response to asynchronous request
            else if ((parsedData.hasOwnProperty(isEmpty))&&(parsedData[isEmpty] === true)) {
                onSuccess();
            }
            // Not an error and no HTML generated
            else {
                commonDef.showError(
                    commonDef.noStatus, /* status */
                    commonDef.locInvalidObjectTitle, /* title */
                    commonDef.locInvalidObjectMessage /* message */
                );
            }
        };
    };

    /**
     * Displays an error message to the user.
     * @param {number} status - Status for the error message. Ignored for now.
     * @param {string} title - Localized title for the error message.
     * @param {string} message - Localized description for the error message.
     */
	commonDef.showError = function (status, title, message) {
        var div = $("<div />")
            .append(
                $("<div />", { id: "showError" })
                    .append(
                        $("<h1 />", { text: title }).prepend(
                            $("<i />", {class: "fas fa-exclamation-circle"})
                        )
                    )
                    .append(
                        $("<p />", {text: message })
                    )
            );
	    vex.dialog.alert({ unsafeMessage: div.html()});
	};

    /**
     * Displays an unprocessed (raw) error (unhandled exception) in a user-friendly format to the user. Raw errors are returned from the server as a complete HTML page.
     * @param {string} html - Complete HTML page describing error (unhandled exception) to display in a pop-up window.
     */
	commonDef.showRawError = function (html) {
	    var txtId = "refullDtlsTxt";
        var div = $("<div />")
            .append(
                $("<div />", { id: "rawError" })
                    .append(
                        $("<h1 />", { text: commonDef.locRawErrorTitle }).prepend(
                            $("<i />", {class: "fas fa-exclamation-circle"})
                        )
                    ).append(
                        $("<p />", {text: commonDef.locRawErrorMessage })
                    ).append(
                        $("<p />")
                            .append(
                                $("<span />", {
                                    id: txtId,
                                    text: commonDef.locRawErrorDetails,
                                    class: "details clickable"
                                }).append(
                                    $("<i />", {class: "fas fa-external-link-alt"})
                                )
                            )
                    )
            );
	    vex.dialog.alert( { unsafeMessage: div.html() } );
	    // add on click event to display full error details
	    var clickable = $("#" + txtId);
	    clickable.on("click", function () {
	        var popup = w.open("", "fed" + String(Date.now()), "scrollbars=1");
	        // HTML returned is ready to be displayed
	        if (_isHtml(html)) { popup.document.write(html); }
	        // HTML returned is not complete, so build page around it
	        else { popup.document.write(_buildHtml(html)); }
	    });

	};

    /**
     * Displays a confirmation message to the user.
     * @param {number} status - Status for the confirmation message. Ignored for now.
     * @param {string} title - Localized title for the confirmation message.
     * @param {string} message - Localized description for the confirmation message.
     * @param {function} onConfirmFunc - Function to call if user confirms. Passed no parameters.
     * @param {function} onCancelFunc - Function to call if user cancels. Passed no parameters.
     */
	commonDef.showConfirmation = function (status, title, message, onConfirmFunc, onCancelFunc) {
        var div = $("<div />")
            .append(
                $("<div />", { id: "showConfirmation" })
                    .append(
                        $("<h1 />", { text: title }).prepend(
                            $("<i />", {class: "fas fa-question-circle"})
                        )
                    )
                    .append(
                        $("<p />", {text: message })
                    )
            );
	    vex.dialog.confirm(
	        {
	            unsafeMessage: div.html(),
	            callback: function (value) {
	                if (value === true) { onConfirmFunc(); }
                    else { onCancelFunc(); }
                }
            }
	    );
	};

    /**
     * Displays a message to the user that is defined through raw HTML.
     * @param {number} status - Status for the message. Ignored for now.
     * @param {string} title - Localized title for the HTML message.
     * @param {Object} html - Html elements, wrapped in JQuery objects to add to message box.
     * @param {function} onShowFunc - Function to call when the HTML message is displayed. Passed no parameters.
     */
	commonDef.showHtmlMessage = function (status, title, html, onShowFunc) {
        var div = $("<div />")
            .append(
                $("<div />", { id: _htmlDialogId })
                    .append(
                        $("<h1 />", { text: title }).prepend(
                            $("<i />", {class: "fas fa-question-circle"})
                        )
                    )
                    .append(
                        html
                    )
            );
        vex.dialog.alert(
            {
                unsafeMessage: div.html(),
                afterOpen: function ($vexContent) {
                    if (onShowFunc) {
                        onShowFunc();
                    }
                }
            }
        );
	};

    /**
     * Retrieves a function that can be executed if an asynchronous (AJAX) request encountered an error (unhandled exception).
     * @returns {function} Function to handle error (unhandled exception).
     */
    commonDef.getOnErrorAjaxFunc = function () {
        return function(jqHXR, textStatus, errorThrown) {
            commonDef.showRawError(jqHXR.responseText);
        };
    };

    /**
     * Makes an asynchronous (AJAX) request to the server.
     * @param {string} ajaxUrl - Url to which request is made.
     * @param {Object} ajaxData - Data sent to server during request.
     * @param {boolean} doStringify - True if the stringify method should be applied to the data sent to the server.
     * @param {function} onSuccess - Function to call if request was successful. May be passed parameters from the returned JSON object.
     * @param {boolean} isForm - True if form is being submitted to server and content type should be changed from JSON to form.
     */
	commonDef.ajax = function (ajaxUrl, ajaxData, doStringify, onSuccess, isForm) {
        $.ajax({
            url: ajaxUrl,
            method: commonDef.ajaxMethod,
            data: (doStringify === true) ? JSON.stringify(ajaxData) : ajaxData,
            contentType: (isForm === true) ? commonDef.formContentType : commonDef.ajaxContentType,
            dataType: commonDef.ajaxDataType,
            success : commonDef.getOnSuccessAjaxFunc(onSuccess),
            error : commonDef.getOnErrorAjaxFunc()
        });
	};

    /**
     * Retrieves a function that performs a callback for the parent/opener window for the current popup window.
     * @param {Object} popupWindow - Popup window that is performing the callback. Must be wrapped in JQuery object.
     * @param {string} popupId - Unique identifier for the popup window. May be "TRUE" if no identifier was provided.
     * @param {number} pk - Primary key used to identify object selected or added in current popup window.
     * @param {string} strRep - String representation for the object selected or added in current popup window.
     */
    commonDef.getPopupCallbackFunc = function (popupWindow, popupId, pk, strRep) {
        /**
        * Called to perform a callback for the parent/opener window for the current popup window.
        * @param {Object} event - Event through which callback is triggered, e.g. link click.
        */
        return function (e) {
            // if event is defined, then prevent event bubbling
            // function may be called without event
            if (e) {
                e.preventDefault();
            }
            var opener = popupWindow.opener;
            // window is disconnected, so try and retrieve opener from session storage
            if (!opener) {
                var unParsedOpener = sessionStorage.getItem(popupId);
                if (unParsedOpener) {
                    opener = JSON.parse(unParsedOpener);
                }
            }
            // window is still connected to its opener
            if (opener) {
                var windowFuncs = opener[commonDef.windowFuncs];
                if (windowFuncs) {
                    var callbackFunc = windowFuncs[popupId];
                    if (callbackFunc) {
                        callbackFunc(
                            pk, /* pk */
                            strRep /* strRep */
                        );
                        return;
                    }
                }
            }
            commonDef.showError(
                commonDef.noStatus, /* status */
                commonDef.locErrorTitle, /* title */
                commonDef.locPopupError /* message */
            );
        };
    };

    /**
     * Close all popups with a unique identifier.
     * @param {uniqueId} uniqueId - Unique identifier of popups to close.
     */
    commonDef.closePopups = function (uniqueId) {
        // all windows with this unique identifiers
        var len = (_openedWindows.hasOwnProperty(uniqueId)) ? _openedWindows[uniqueId].length : 0;
        for (var i = 0; i < len; i++) {
            var popup = _openedWindows[uniqueId][i];
            if (!popup.closed) {
                popup.close();
            }
            _openedWindows[uniqueId][i] = null;
        }
        _openedWindows[uniqueId] = [];
    };

    /**
     * Opens a new window for a popup.
     * @param {string} url - URL to load into new window for popup.
     * @param {number} uniqueId - Unique numerical identifier for parent of new window. Used as a key in the dictionary storing all windows opened. May be null if popup does not need to connect with parent window.
     * @param {bool} makeAbsolute - True if URL should be made absolute, false otherwise.
     * @returns {Object} New window for popup.
     */
    commonDef.openPopup = function (url, uniqueId, makeAbsolute) {
        if (makeAbsolute === true) {
            url = commonDef.makeAbsolute(url /* url */);
        }
        // new window for popup should be connected with parent window (from which popup was initiated)
        if (uniqueId) {
            var name = new Date().valueOf();
            var params = "menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes";
            var connectedPopup = w.open(url, name, params);
            connectedPopup[commonDef.windowUniqueId] = uniqueId;
            if (!_openedWindows.hasOwnProperty(uniqueId)) {
                _openedWindows[uniqueId] = [];
            }
            _openedWindows[uniqueId].push(connectedPopup);
            return connectedPopup;
        }
        // new window for popup is not connected with parent window
        else {
            var disconnectedPopup = w.open(url);
            return disconnectedPopup;
        }
    };

    /**
     * Shows a message to the user indicating that their browser is unsupported.
     */
    commonDef.showUnsupportedBrowser = function () {
        commonDef.showError(
            commonDef.noStatus, /* status */
            commonDef.locErrorTitle, /* title */
            commonDef.locBrowserUnsupported /* message */
        );
    };

    /**
     * Retrieve a value from the URL's querystring.
     * @param {string} queryStringKey - Key used to identify the value in the URL's querystring.
     * @returns {Object} Value from the URL's querystring, or null if key is not found in the querystring.
     */
    commonDef.getFromQueryString = function (queryStringKey) {
        var queryStringValue = null;
        if (typeof URLSearchParams !== "function") {
            commonDef.showUnsupportedBrowser();
        }
        else {
            var urlSearchParams = new URLSearchParams(w.location.search);
            queryStringValue = urlSearchParams.get(queryStringKey);
        }
        return queryStringValue;
    };

    /**
     * Checks whether a window is displayed as a popup.
     * @param {string} popupKey - Key used to identify the popup value in the URL's querystring.
     * @returns {boolean} True if window is displayed as a popup, false otherwise.
     */
    commonDef.isPopup = function (popupKey) {
        var queryStringValue = commonDef.getFromQueryString(popupKey /* queryStringKey */);
        return (queryStringValue != null);
    };

    /**
     * Retrieves a unique identifier for the window if it is displayed as a popup.
     * @param {string} popupIdKey - Key used to identify the unique identifier value in the URL's querystring.
     * @returns {string} Unique identifier for the window, if it is displayed as a popup, null otherwise.
     */
    commonDef.getPopupId = function (popupIdKey) {
        var queryStringValue = commonDef.getFromQueryString(popupIdKey /* queryStringKey */);
        return (queryStringValue != null) ? queryStringValue : null;
    };

    /**
     * Adds the unique popup identifier into the form input.
     * @param {Object} windowElem - Element that represents the window in which form is rendered.
     * @param {string} popupValue - Queryset GET parameter value used to indicate whether form is being rendered as a popup.
     * @param {string} popupIdKey - Queryset GET parameter used to indicate the unique identifier for the form that is being rendered as a popup.
     * @param {Object} popupField - Form input field into which the unique popup identifier will be added.
     * @param {Object} formInPopup - Form into which input field storing popup identifier will be added. Must be wrapped in JQuery object.
     */
    commonDef.addPopupIdToForm = function (windowElem, popupValue, popupIdKey, popupField, formInPopup) {
        // looking for unique identifier for popup window referenced by the opener through Ishra.Common.getPopupCallbackFunc(...)
        // popup windows that are opened by Ishra.Common.openPopup(...) have the window property set
        var uniqueId = windowElem[commonDef.windowUniqueId];
        // if user navigated to a link in the popup window, then window property may be lost
        // so check if property is part of the querystring
        if (uniqueId == null) {
            uniqueId = commonDef.getPopupId(popupIdKey /* popupIdKey */);
        }
        // if unique identifier was not located, then just use default value, e.g. TRUE indicating the popup
        var popupId = (uniqueId != null) ? uniqueId : popupValue;
        // add hidden field containing popup identifier into form
        formInPopup.append(
            $("<input />", {
                id: popupField,
                name: popupField,
                type: "hidden"
            }).val(popupId)
        );
        // store the window opener in session storage, in case it is lost during redirects, POST requests, etc.
        sessionStorage.setItem(popupId, JSON.stringify(windowElem.opener));
    };

    /**
     * Adds a blank value into the form input to indicate that the form is not being rendered as a popup.
     * @param {Object} popupField - Form input field into which the blank value will be added.
     */
    commonDef.nullifyPopupIdInForm = function (popupField) {
        $("#popupField").val("");
    };

	/**
	* Initializes elements with the Select2 package for client-side only (i.e. no requests sent to server) that in a containing element.
	* @param {string} selector - JQuery selector for the elements that should be initialized with the Select2 package.
	* @param {Object} container - Container for Select2 elements to initialize. If defined, must be wrapped in JQuery object. May be undefined.
	* @see {@link https://select2.org/}
	* @see {@link https://github.com/select2/select2}
	*/
	commonDef.initPassiveSelect2ElemsInContainer = function (selector, container) {
        // container for Select2 elements is defined
        if (container) {
            container.find(selector).select2();
        }
        // container for Select2 elements is undefined
        else {
            $(selector).select2();
        }
    };

	/**
	* Initializes elements with the Select2 package for client-side only (i.e. no requests sent to server).
	* @param {string} selector - JQuery selector for the elements that should be initialized with the Select2 package.
	* @see {@link https://select2.org/}
	* @see {@link https://github.com/select2/select2}
	*/
	commonDef.initPassiveSelect2Elems = function (selector) {
        commonDef.initPassiveSelect2ElemsInContainer(
            selector, /* selector */
            null, /* container */
        );
    };

	/**
	* Disables an element that was initialized with the Select2 package.
	* @param {string} selector - JQuery selector for the elements wrapped in Select2 package that should disabled.
	* @see {@link https://select2.org/}
	* @see {@link https://github.com/select2/select2}
	*/
	commonDef.disableSelect2Elem = function (selector) {
        $(selector).prop("disabled", true);
	};

	/**
	* Retrieves the function to call to handle the response for the JQuery UI autocomplete package.
	* @param {string} noResultsMsg - Text to display if no data is returned through the autocomplete.
	* @returns {function} Response function for the JQuery UI autocomplete package.
	* @see {@link https://api.jqueryui.com/autocomplete/#event-response}
	*/
	commonDef.getAutocompleteResponseFunc = function (noResultsMsg) {
        return function (event, ui) {
            if (!ui.content.length) {
                var noResult = { value:"", label: noResultsMsg };
                ui.content.push(noResult);
            }
        };
	};

	/**
	* Copies errors from a hidden element to a visible element. Used for example when ID fields are hidden, and corresponding Autocomplete fields are displayed.
	* @param {Object} fromInput - Hidden input element from which to copy errors.
	* @param {Object} toInput - Visible input element to which to copy errors.
	*/
	commonDef.copyErrorsFromInput = function (fromInput, toInput) {
        var errorSelector = "ul.errorlist";
        var fromErrors = fromInput.siblings(errorSelector);
        // errors exist to copy
        if (fromErrors.length === 1) {
            var toErrors = toInput.siblings(errorSelector);
            // errors exist in destination
            if (toErrors.length === 1) {
                toErrors.append(fromErrors.children());
            }
            // errors don't exist in destination
            else {
                var toContainer = toInput.parent().first();
                toContainer.prepend(fromErrors);
            }
        }
	};

	/**
	* Hides a form if it contains an input that indicates that the form is deleted.
	* @param {Object} containerToHide - Containing element for form. Must be wrapped in JQuery object.
	*/
	commonDef.hideFormIfDeleted = function (containerToHide) {
	    var deletedField = containerToHide.find(".formdel");
	    if (deletedField.length === 1) {
	        var isDeleted = deletedField.is(":checked");
	        if (isDeleted === true) {
	            containerToHide.hide();
	        }
	    }
	};

    /**
     * Retrieves a string that can be append to a URL to pass a GET parameter (both name and value).
     * Assumes that a querystring is already defined for the URL, i.e. the ?...  portion is already defined.
     * @param {string} paramName - Name of GET parameter.
     * @param {Object} paramValue - Value for GET parameter.
     * @returns {string} String for GET parameter name and value in the format: "&paramName=paramValue.
     */
    commonDef.getQueryStringParamNameAndValue = function (paramName, paramValue) {
        return "&" + paramName + "=" + paramValue;
    };

    /**
     * Retrieves the input element through which text searches are performed in autocomplete.
     * @param {Object} formContainer - Containing element for form in which input element exists. Must be wrapped in JQuery object.
     * @param {string} selector - String representing JQuery selector through which input element is identified in the containing form.
     * @returns {Object} Input element through which text searches are performed in autocomplete.
     */
    commonDef.getAutocompleteSearchElem = function (formContainer, selector) {
        if (formContainer) {
            return formContainer.find(selector);
        }
    };

    /**
     * Retrieves the input element in which hidden ID is stored during autocomplete.
     * @param {Object} formContainer - Containing element for form in which input element exists. Must be wrapped in JQuery object.
     * @param {string} selector - String representing JQuery selector through which input element is identified in the containing form.
     * @returns {Object} Input element through which hidden ID is stored during autocomplete.
     */
    commonDef.getAutocompleteIdElem = function (formContainer, selector) {
        if (formContainer) {
            return formContainer.find(selector);
        }
    };

    /**
     * Show that a JQueryUI Autocomplete widget is in a state considered OK, e.g. when a user has selected one of its suggestions.
     * @param {Object} searchInputElem - Input element through which text searches are performed in autocomplete. Must be wrapped in JQuery object.
     * @see {@link https://api.jqueryui.com/autocomplete/}
     */
    commonDef.showAutocompleteOk = function (searchInputElem) {
        searchInputElem.removeClass(_notOkCssClass);
        searchInputElem.addClass(_okCssClass);
    };

    /**
     * Show that a JQueryUI Autocomplete widget is in a state considered NOT OK, e.g. when a user has changed the text in the
     * search element but has not yet selected a corresponding suggestion.
     * @param {Object} searchInputElem - Input element through which text searches are performed in autocomplete. Must be wrapped in JQuery object.
     * @see {@link https://api.jqueryui.com/autocomplete/}
     */
    commonDef.showAutocompleteNotOk = function (searchInputElem) {
        searchInputElem.removeClass(_okCssClass);
        searchInputElem.addClass(_notOkCssClass);
    };

    /**
     * Initializes the JQueryUI Autocomplete widget to asynchronously search for and loads records.
     * @param {Object} searchInputElem - Input element through which text searches are performed in autocomplete. Must be wrapped in JQuery object.
     * @param {Object} idInputElem - Input element in which hidden ID value is stored during autocomplete. Must be wrapped in JQuery object.
     * @param {string} ajaxUrl - Url through which records can be loaded asynchronously for autocomplete.
     * @param {string} extraCssClass - Additional CSS class that is added to containing .ui-autocomplete element.
     * @see {@link https://api.jqueryui.com/autocomplete/}
     */
    commonDef.initAutocomplete = function (searchInputElem, idInputElem, ajaxUrl, extraCssClass) {
        // searching with autocomplete
        searchInputElem.autocomplete({
            classes: {"ui-autocomplete": extraCssClass},
            minLength: commonDef.autoCompleteChars,
            source: function (request, response) {
                _getAutocompleteClearHiddenInputIdFunc(idInputElem /* idInput */)();
                // adds styling to search box, to indicate not yet a successful selection
                commonDef.showAutocompleteNotOk(searchInputElem /* searchInputElem */);
                _getAutocompleteLoadFunc(response /* callbackFunc */, ajaxUrl /* ajaxUrl */)(
                    request.term /* searchTerm */
                );
            }, /* source */
            select: function(event, ui) {
                var item = ui.item;
                var id = item.value;
                var name = item.label;
                if (id) {
                    _getAutocompleteSetElements(idInputElem /* idInputElem */, searchInputElem /* searchInputElem */)(
                        id, /* id */ name /* name */
                    );
                    // adds styling to search box, to indicate successful selection
                    commonDef.showAutocompleteOk(searchInputElem /* searchInputElem */);
                } else {
                    _getAutocompleteClearHiddenInputIdFunc(idInputElem /* idInput */)();
                    // adds styling to search box, to indicate not yet a successful selection
                    commonDef.showAutocompleteNotOk(searchInputElem /* searchInputElem */);
                }
                event.preventDefault();
            }, /* select */
            response: commonDef.getAutocompleteResponseFunc("No matches found" /* noResultsMsg */) /* response */
        });
        // autocomplete fields are already populated during initialization
        if (idInputElem.val() && searchInputElem.val()) {
            // adds styling to search box, to indicate previous successful selection
            commonDef.showAutocompleteOk(searchInputElem /* searchInputElem */);
        }
    };

    // Define Fdp.Common
	fdpDef.Common = commonDef;

	return fdpDef;
}(Fdp || {}, window.jQuery, window, document));
