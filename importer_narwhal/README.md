# Overview
The 'narwhal importer' is built on the django-import-export package.

# Features
- Traceable error reporting on a pre row level for both validation errors and database errors
- Foreign key lookups by pk, external identifier, or value (where practical)
- Flexible boolean values (e.g. 'checked' for True)
- Update existing records
- Delete previous batch

# Usage
Use the 'narwhal_import' management command to use the importer.

# TODO
- Template generator
- Background task manager for long running batches
- GUI front end
- Guest / Host / Admin access control filtering

# External IDs
On import
Row level
Cell / relation level

On update
Row level
Cell / relation level

Uniqueness
