# Changelog

All releases will be logged in this file.

## [1.2.1] - 2021-07-06
Bug fix release

### Fixed
- Address issues caused by Django username case sensitivity and Azure Active Directory case *in*sensitivity.

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