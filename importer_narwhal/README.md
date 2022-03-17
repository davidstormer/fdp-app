# Overview
The 'narwhal importer' is based on the django-import-export package.

# Features
- Traceable error reporting on a pre row level for both validation errors and database errors
- Foreign key lookups by pk, external identifier, or value 
- Flexible boolean values (e.g. 'checked' for True)
- Update existing records

# Usage
Use the 'narwhal_import' management command to use the importer.

# TODO
- Bulk delete previous batch
- Template generator
- Background task manager for long running batches
- GUI front end
