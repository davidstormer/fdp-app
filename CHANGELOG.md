# Changelog

All releases will be logged in this file.


## [2.1.0] - 2021-10-12

### Added
- Add demo content via fixture file
- Add database schema report file data_model.md

### Changed
- Add EULA upload feature and change splash page feature to be separate from 2FA workflow pages
- Rename content identifier field label from "Number" to "Identifier"

### Removed
- Officer profile page: Remove 'Active from ...' feature


## [2.0.0] - 2021-09-21
Major release

### Added
- Add session timeout reminder popup
- Add photo upload to Add Person form
- Add app version to user interface
- Add indication when fields are required
- Make attachment validation settings configurable on a per-instance basis (via settings.py)

### Changed
- Merge Add Person forms (is law enf and not is law enf)
- Accept .webm format for source attachments
- Make name field on content not required
- Make link field on content unique

### Removed
- Remove code field from Grouping

### Fixed
- Fix typo of 'Reasons' field in encounters

### Security
- FDP-2021-006: Bulk importer: Remove file download capability from file serializers
- FDP-2021-003: Email enumeration via password reset
- FDP-2021-001: CSP largely ineffective against injection attacks
- FDP-2021-006: Admin SSRF signifies access to internal network
- FDP-2021-005: Pre-auth stored XSS in CSP logs in admin panel
- FDP-2021-004 & FDP-2021-002: Account lockout on failed login attempts
- Upgrade Django to 3.1.12 (security release) and cryptography to 3.3.2 (security release)
- Freeze all package dependencies in requirements.txt
- FDP-2021-007: Fix FDP_SOCIAL_AUTH_OAUTH2_WHITELISTED_DOMAINS setting has no effect

## [1.2.4] - 2021-07-26
Field validation changes

### Changed
- Phone number fields in Person Contact and Groups: remove validation
- Bulk importer: Remove phone number field transformations (Person Contact and Groups)

NOTE: this release makes a change to database constraints, allowing longer phone_number fields. Run
`python manage.py migrate` to apply these changes.

## [1.2.3] - 2021-07-26
Security release

### Security
- FDP-2021-008: Set AXES_PASSWORD_FORM_FIELD to 'auth-password'

## [1.2.2] - 2021-07-21
Bug fix release

### Fixed
- Bulk importer: Add missing Case Court field to Content import serializer
- Bulk importer: Add missing situational role to Content Person & Incident Person serializers
- Bulk importer: Change Person serializer "exact_birth_date" to "birth_date_start_range" and "birth_date_end_range"

## [1.2.1] - 2021-07-06
Bug fix release

### Fixed
- BREAKING CHANGE: Address issues caused by Django username case sensitivity and Azure Active Directory case *in*sensitivity.

### Upgrading notes
WARNING: After applying this update, if an instance contains duplicate usernames with case variations (e.g. 'User@example.com' and 'user@example.com') these users will not be able to log in. To remedy this, rename the disused duplicate to a unique name (e.g. rename 'User@example.com' to 'User-dupe@example.com') directly in the SQL database. Renaming is preferred over deleting the account. There could be valuable history associated with the account, which would be lost if it were deleted.

## [1.2.0] - 2021-06-22
Bulk importer changes

### Added
- Bulk importer: Add page showing importer "serializer" templates and fields at /datawizard/import-templates
- Bulk importer: Add bulk importer "serializers" for handling content-person links, content identifiers, attachments, person-incident links
- Bulk importer: Update content serializer to take comma separated external attachment IDs for creating links


## [1.1.1] - 2021-04-09
Bug fix release

### Fixed
- Fix 500 error on content search (/changing/content/) with search queries that look like hyphenated dates (e.g. 01-01 or 01-01-01)

## [1.1.0] - 2021-04-08

### Added
- Bulk importer: Add person-title serializer.
- Bulk importer: Split date into individual. components for person-grouping serializer. Add is_inactive and as_of field support for person-grouping serializer.
- Bulk importer: Add person payment serializer.

### Fixed
- Bulk importer: Performance improvements (disable versioning of records, set UI progress status poll time from 1/2 to 30 seconds).
- Bulk importer: Fix missing MIME type support for xlsx files when server doesn't have it (i.e. Azure).

### Changed
- Security: Update Django from version 3.1.3 to 3.1.7
- Move settings.py to settings_example.py to prevent clobbering of custom configurations on pulls and resets.

## [1.0.0] - 2021-03-18
First formal release, including recent changes since initial code base was established with first instance.

### Added
- Configuration specific 2FA fallback logic unitish tests
- Serializers for link between People and Grouping (e.g. career segments)

### Fixed
- 500 error on object creation pages like location and attachments (static loader)
- Fix compatibility between Django data wizard and object-based file storage backend
