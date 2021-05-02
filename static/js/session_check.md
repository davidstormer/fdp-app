# Code trace to check user session expiry in the FDP system

## Synchronous page load

Variable initialized:

    _checkBackAfterFullSession=true;

In this example, session checks are initialize with 4 minute sessions and with notifications starting at 3 minutes to expiry:

    Fdp.Common.initSessionExpiryCheck(sessionAge=240);
    ...
    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=240000, isSessionAgeUnknown=false)();
    ...
    _scheduleSessionExpiryCheck(expectedSessionAgeMilliseconds=240000, isAlreadyClosed=false); 

Control statement succeeds for 4 minutes is greater than 3 minutes:

    _checkBackAfterFullSession=false;
    ...
    _hideSessionExpiry();
	
If the dialogue is visible, then:

    _getOnHideSessionExpiryFunc()();		
    _checkBackAfterFullSession=true;

If the dialogue is not visible, then:

    _checkBackAfterFullSession=true;			

Wait for 1 minute via setTimeout(...).

    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=180000, isSessionAgeUnknown=false)();
    ...
    _scheduleSessionExpiryCheck(expectedSessionAgeMilliseconds=180000, isAlreadyClosed=false); 

Control statement fails for 3 minutes is greater than 3 minutes:

    _showSessionExpiry(millisecondsLeft=180000);

The dialogue is not yet visible, so display the dialogue:

    _getOnShowSessionExpiryFunc(millisecondsLeft=180000, initOkButtonOnClick=true)();

Add the one-time event handler to the OK button, and the session is confirmed to still be active.

Wait for 30 seconds via setTimeout(...).

    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=150000, isSessionAgeUnknown=false)();
    ...
    _scheduleSessionExpiryCheck(expectedSessionAgeMilliseconds=150000, isAlreadyClosed=false);

Control statement fails for 2 minutes and 30 seconds is greater than 3 minutes:

    _showSessionExpiry(millisecondsLeft=150000);

The dialogue is already visible:

    _getOnShowSessionExpiryFunc(millisecondsLeft=150000, initOkButtonOnClick=false)();

The session is confirmed to still be active.

Wait for 30 seconds via setTimeout(...), then another 30 seconds, and so on until only a minute is left.
	
    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=120000, isSessionAgeUnknown=false)();
    ...
    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=90000, isSessionAgeUnknown=false)();
    ...
    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=60000, isSessionAgeUnknown=false)();
    ...
    _scheduleSessionExpiryCheck(expectedSessionAgeMilliseconds=60000, isAlreadyClosed=false);

Control statement fails for 1 minute is greater than 3 minutes:

    _showSessionExpiry(millisecondsLeft=60000);

The dialogue is already visible:

    _getOnShowSessionExpiryFunc(millisecondsLeft=60000, initOkButtonOnClick=false)();

The session is confirmed to still be active.

Wait for 5 seconds via setTimeout(...), then another 5 seconds, and so on until no time is left.

    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=55000, isSessionAgeUnknown=false)();
    ...
    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=0, isSessionAgeUnknown=false)();
    ...
    _scheduleSessionExpiryCheck(expectedSessionAgeMilliseconds=0, isAlreadyClosed=false);

Control statement fails for 0 seconds is greater than 3 minutes:

    _showSessionExpiry(millisecondsLeft=0);

The dialogue is already visible:

    _getOnShowSessionExpiryFunc(millisecondsLeft=0, initOkButtonOnClick=false)();

The session is confirmed to have expired.
	
## Pressing OK

If the user presses the OK button after its one-time event handler has been attached:

    _checkBackAfterFullSession = false;

If the HTML5 data-* attribute on the OK button is set to true to indicate that the session is still active:

    _renewUserSession()
	
Then, regardless of whether the session is active or expired:

    _getOnHideSessionExpiryFunc()();

Control statement fails for false is true.

    _checkBackAfterFullSession = true;

## Closing dialogue without pressing OK

If the user closes the dialogue without pressing the OK button:

    _getOnHideSessionExpiryFunc()();

Control statement succeeds for true is true.

    _checkBackAfterFullSession = true;

Wait for a full session length via setTimeout(...) and then restart session expiry checks:

    _getSessionExpiryCheckFunc(sessionAgeMilliseconds=0, isSessionAgeUnknown=true)();
    ...
    _scheduleSessionExpiryCheck(expectedSessionAgeMilliseconds=..., isAlreadyClosed=true);
