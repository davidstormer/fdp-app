# Changelog

All releases are logged in this file.

## [6.0.3] - 2022-08-22

### Changed
- Importer: Fix unrecognized column error on simple foreign key fields with '__external_id' extension

## [6.0.2] - 2022-08-11

### Changed
- Minor typographical and user interface fixes

## [6.0.1] - 2022-08-09

### Changed
- Importer: Handle Microsoft Byte Order Mark on CSV import sheets

## [6.0.0] - 2022-08-03

### Added
- New Person search page with improved usability ('roundup' search)
- New Person search algorithm that better handles middle names, abbreviations, variation in spelling and 
  punctuation ('roundup' search)
- Newly designed bulk importer workflow pages with more specific error reporting and guidance
- Bulk importer columns documentation page
- Command line interface for bulk importer
- Command line data exporter tool (no Web UI yet)
- Custom text blocks on site footer and profile pages
- Help text for data fields on editing pages
- Optional default types and tags (available on installation)

### Changed
- Add Group field to Person Title records
- Rename "is inactive" field to "ended unknown date"
- Add "ended unknown date" to date fields on PersonIdentifier, PersonRelationship, PersonPayment, 
  GroupingRelationship, PersonTitle, PersonGrouping, ContentCase, and Incident; and add "at least since" field on 
  ContentCase, and Incident
- Fix relationship types not updating on Person and Group editing pages
- Add audit log when AAD attempted logins have incorrect domain (security)
- Fix carriage returns in description text not showing on detail pages
- Increase default max failed password attempts and decrease default lockout time
- Fix empty parens when rank dates set to all zeros
- Add missing 'host only' filter option in Advanced Admin listing pages
- Rename "Officer" to "Person" on homepage, and officer search pages

### Removed
- "Snapshot" feature on person profile page now disableable via settings.py setting
- Prior version of Officer search disabled by default, but reenablable via settings.py setting

### Security patches
- Upgrade Django to 3.2 LTS release from deprecated 3.1 release channel
- PyJWT 2.4.0
- sqlparse 0.4.2
- lxml 4.9.1

### Upgrading notes
The new 'roundup' search requires that the TrigramSimilarity extension be enabled in PostgreSQL, and adds a new 
"full_text" field. This change is handled in a migration file. There are several other new fields and a field rename.

To accomplish all of this database migrations must be run during upgrade:
```shell
python3 manage.py migrate
```
You may get 500 errors until you do this.

In addition, the "full_text" field must be populated during upgrade using a custom management command:

```shell
python3 manage.py reindex_search
```

This may take a while to run. Search will not function properly until this is done. Note that moving forward the 
full_text field automatically updates with any new or updated records, so it is unnecessary to run this command 
again in the future after the upgrade.

## [5.0.1] - 2022-03-07

### Changed

- Wholesale batch listing: fix incorrect sorting order
- Wholesale: fix backward-incompatibility with existing external ids table field use
- Changing pages: fix slow scroll animation when adding new items in inline formsets on changing pages

## [5.0.0] - 2022-02-22

### Added

  - Officer profile page: Add contact info to identification section
  - Edit records directly from officer profile page
  - Add new import tool ('wholesale' importer)
  - Add support center link to all pages for administrative users
  - Bulk data manipulation management commands: bulk_delete, export_external_ids, bulk_perms_host_only, 
    bulk_update_groups
  - Add functional testing framework for developers

### Changed

  - Attachments: add mp3 as valid upload file in default settings -- and expand list with other common formats
  - Change "as of" field on dates to "at least since" (see migration notes below)
  - Officer profile page:
    - Redesign identification section for improved readability
    - Group membership show officer's relation to group, link to group, and print "until unknown-end-date" when end 
      date is unknown
    - Payroll section, collapse out of the way by default, and print hyphens when values are empty
    - Redesign Associates section to: reflect subject object order, add dates of relationship, and link to 
      associates' profiles
    - Rename "Misconduct" to "Known incidents"
    - Reverse order of incidents
    - In incident details show persons' situation role and rename "other officers involved" to "others involved"
  - Upgrade Django to 3.1.14, and sqlparse to 0.4.2 (security releases)

### Removed

  - Officer profile: Bolding of various data points under certain conditions in identification section.

### Upgrading notes

Changes to the associates section of the officer profile page require that relationship types (i.e. predicates) be 
updated to include the preposition (e.g. 'of' 'with' 'for'). For example "Father" should be changed to "Father of" 
and "Sibling" should be changed to "Sibling with". These must be updated manually.

The new wholesale importer feature requires a database migration. Run:
```shell
python3 manage.py migrate
```
to apply these migrations to the database. You may get a 500 error until you do this.


## [4.0.0] - 2021-12-14

### Added
- Add federated login page
- Add license file to project root dir
- Add vagrant for local development / demo sandbox environment
- Add is law enforcement check-box for Groups - update search to only show marked groups

### Changed
- Make static and media files be located in separately define storage containers
- Make is law enforcement checkbox a select box and make it a required field

### Upgrading notes

**Groups**

The new is_law_enforcement field on Groups requires a database migration. Run:
```shell
python3 manage.py migrate
```
to apply these migrations to the database. *You will get a 500 error until you do this.*

The search *won't return any groups* that aren't set as law enforcement. To bulk set all existing groups as law 
enforcement run the following code in the shell:

```python
from core.models import Grouping
def set_all_groups_to_is_law_enforcement_true():
    for group in Grouping.objects.all():
        group.is_law_enforcement = True
        group.save()
        print(f"Updated {group} to is_law_enforcement = True")

set_all_groups_to_is_law_enforcement_true()
```

**Storage containers**

The static and media storage locations are separately defined now. Add these settings in the new environment 
variables:

| Environment Variable                  | Azure Key Vault name                 |
| ------------------------------------- | ------------------------------------ |
| FDP_AZURE_STATIC_STORAGE_ACCOUNT_NAME | FDP-AZURE-STATIC-STORAGE-ACCOUNT-KEY |
| FDP_AZURE_MEDIA_STORAGE_ACCOUNT_NAME  | FDP-AZURE-MEDIA-STORAGE-ACCOUNT-KEY  |

*The system will not function until these are added.*

You can duplicate the same settings if you'd like to continue using the same container. 

## [3.0.0] - 2021-10-12

### Added
- Add EULA upload feature and change splash page feature to be separate from 2FA workflow pages
- Add demo content via fixture file
- Add database schema report file data_model.md

### Changed
- Rename content identifier field label from "Number" to "Identifier"

### Removed
- Officer profile page: Remove 'Active from ...' feature

### Upgrading
The new EULA feature requires a database migration. Run:
```shell
python3 manage.py migrate
```
to apply these migrations to the database. You will get a 500 error until you do this.

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
