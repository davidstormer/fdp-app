# Changelog

All releases will be logged in this file.

## [1.2.4] - 2021-07-26
Field validation changes

### Changed
- Phone number fields in Person Contact and Groups: remove validation
- Bulk importer: Remove phone number field transformations (Person Contact and Groups)

NOTE: this release makes a change to database constraints, allowing longer phone_number fields. Run
`python manage.py migrate` to apply these changes.

## [1.2.3] - 2021-07-26
Security release

### Fixed
- Axes: Set AXES_PASSWORD_FORM_FIELD to 'auth-password'

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