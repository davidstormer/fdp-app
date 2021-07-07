# Client-side code trace to check for user session expiry in the FDP system

## Synchronous page load

Initialization on synchronous page loads is performed by a call from the *onready* template block in the *base.html* template:

    Fdp.Common.initSessionExpiryCheck(... /* sessionAge */);

During initialization, the expected session expiry is placed into both local storage and a variable through:

    _updateSessionExpiry(false /* isLogout */);

Since local storage is shared between windows, a new value will overwrite any existing value with the assumption that the newest value is the most current excepted session expiry.

Next, an event listener is added to listen for changes made to the local storage by other windows.

    _addSessionExpiryUpdateListener();

A loop of continuous checks is started, scheduled to run every second using *setInterval(...)* and to call:

    _checkSessionExpiry(); 

During each check, the flag *_checkLocalStorageForSessionExpiry* is used to determine if the variable containing the expected session expiry is considered to be current, or if the value in the local storage has been changed, possibly through another window. This flag is kept up-to-date through the event listener *_addSessionExpiryUpdateListener(...)*.

Once the most current expected session expiry is known, the Document Object Model (DOM) is optionally manipulated to communicate to the user about the state of their user session: 

    _changeDomForSessionExpiry();

This function uses a series of variables to keep track of its DOM manipulations, including *_isSessionExpiryDialogueDisplayed* and *_isSessionExpiryInCountdown*.

## DOM Manipulation

The *_showModalDialogueForSessionExpiry(...)* function displays the modal dialogue to the user indicating either that their session is about to expire or that it has already expired. In this function, a check is made to see if DOM manipulations are paused, in cases such as to allow an asynchronous session renewal to complete: 

    if (_neverShowSessionExpiry !== true) {...}

The callback function used after the modal dialogue is displayed implements a loop using *setInterval(...)* to allow time for the DOM manipulation to complete so that the dialogue is accessible:

    // DOM manipulation is complete
    if ($(_okButtonSelector).length > 0) { ... }
    // DOM manipulation is not yet complete
    else {
        ...
        var loopHandle = null;
        ...
        function waitForOkButton(){
            // DOM manipulation is complete
            if ($(_okButtonSelector).length > 0) {
                clearInterval(loopHandle);
                ...
            }
        };
        loopHandle = setInterval(waitForOkButton, ...);

Depending on the context in which the modal dialogue is displayed and its contents customized, the primary button, i.e. the OK button, on it, may have an event handler attached to it that reloads the page forcing a login, or renews the user's session asynchronously. 

## Asynchronous requests

With every asynchronous request, the user's session is updated on the server. To keep the client-side session expiry synchronized:

    ...
    ajaxStop(function () {
    ...        
        _updateSessionExpiry(false /* isLogout */);
        ...

## Django Data Wizard package

Asynchronous requests made through the Django Data Wizard package via the *Fetch()* API do not by default update the client-side known session expiry. To address this, a call is made in *data_wizard_progress.js*:

    Fdp.Common.updateSessionExpiry();

## Logging out

An event handler is attached to all HTML elements that a user may click to request logging out of their user session. This event handler is added to all elements with the CSS class *onlogout* through the *_addOnLogout(...)* function and will update the client-side session expiry before the synchronous request to log out is sent to the server: 

    _updateSessionExpiry(true /* isLogout */);

## Closing the dialogue

The modal dialogue is anticipated to be closed whenever the user renews their session or navigates to the login page. In some cases, the modal dialogue may be closed without the user renewing or intending to renew their session.

To prevent the modal dialogue from being displayed as part of the next session expiry check a second after it is closed, the *_isSessionActiveWhenClosed* variable is used to keep track of the state of the user session when the modal dialogue was last closed:

    ...
    var isSessionExpiryInCountdown = _isSessionExpiryInCountdown;
    ...
    _isSessionActiveWhenClosed = isSessionExpiryInCountdown;
    ....

When this variable is set to *null* it is ignored.

When this variable is set to *true*, then the modal dialogue was last closed with the user's session still active.

When this variable is set to *false*, then the modal dialogue was last closed when the user's session had already expired.

If the modal dialogue is closed while the user's session is still active, then the modal dialogue will not be displayed again, unless the user's session expires, or it is renewed:

    ...
    if (_isSessionActiveWhenClosed !== false) {
        _showModalDialogueForSessionExpiry(_changeDomForSessionExpired /* onShowFunc */);
    }
    ...

Conversely, if the modal dialogue is closed after the user's session expires, then the modal dialogue will not be displayed again, unless the user's session becomes active again, or it is renewed:

    ....
    if (_isSessionActiveWhenClosed !== true) {
        _showModalDialogueForSessionExpiry(
            _getChangeDomForSessionExpiryCountdownFunc(millisecondsLeft /* millisecondsLeft */) /* onShowFunc */
        );
    }
    ...
