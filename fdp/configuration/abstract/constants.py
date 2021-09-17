"""

Please DO NOT modify!

This file is imported and provides definitions for the various settings files.

Make any customizations in the main settings.py file.

Used to define constants that are referenced throughout the various settings files.

"""
#: Authentication backend for Django Axes package: https://django-axes.readthedocs.io/en/latest/
CONST_AXES_AUTH_BACKEND = 'axes.backends.AxesBackend'


#: Django's default database-driven authentication backend
CONST_DJANGO_AUTH_BACKEND = 'django.contrib.auth.backends.ModelBackend'


#: Middleware handling Django Two-Factor Authentication when hosting in a Microsoft Azure environment.
CONST_AZURE_OTP_MIDDLEWARE = ['fdp.middleware.azure_middleware.AzureOTPMiddleware']


#: Name of Django app to add into INSTALLED_APPS setting to support authentication through Azure Active Directory.
#: Django Social Auth: https://python-social-auth.readthedocs.io/en/latest/configuration/django.html
CONST_AZURE_AUTH_APP = 'social_django'


#: Additional context processors to add into TEMPLATES setting to support authentication through Azure Active Directory.
#: Django Social Auth: https://python-social-auth.readthedocs.io/en/latest/configuration/django.html
CONST_AZURE_TEMPLATE_CONTEXT_PROCESSORS = [
    'social_django.context_processors.backends',
    'social_django.context_processors.login_redirect'
]


#: Authentication backend for Azure Active Directory
#: See: https://python-social-auth.readthedocs.io/en/latest/backends/azuread.html
CONST_AZURE_AUTH_BACKEND = 'social_core.backends.azuread_tenant.AzureADTenantOAuth2'


#: Value for provider that will define a social authentication record linked to a user authenticated who is
#: through Azure Active Directory.
#: See: https://python-social-auth.readthedocs.io/en/latest/backends/azuread.html
CONST_AZURE_AD_PROVIDER = 'azuread-tenant-oauth2'


#: Value for the default maximum number of bytes that a user-uploaded file can have for an instance of the
# Eula (end-user license agreement) model.
CONST_MAX_EULA_FILE_BYTES = 104857600


#: Value for the default maximum number of bytes that a user-uploaded file can have for an instance of the
# WholesaleImport model.
CONST_MAX_WHOLESALE_FILE_BYTES = 104857600


#: Value for the default maximum number of bytes that a user-uploaded file can have for an instance of the Attachment
# model.
CONST_MAX_ATTACHMENT_FILE_BYTES = 104857600


#: Value for the maximum number of bytes that a user-uploaded file can have for an instance of the Person Photo model.
CONST_MAX_PERSON_PHOTO_FILE_BYTES = 2097152


#: A list of tuples that define the types of user-uploaded files that are supported for an instance of the
# Eula (end-user license agreement) model. Each tuple has two items: the first is a user-friendly short description of
# the supported file type; the second is the expected extension of the supported file type.
CONST_SUPPORTED_EULA_FILE_TYPES = [
    ('Adobe PDF', 'pdf'), ('Microsoft Word 97-2003', 'doc'), ('Microsoft Word 2007+', 'docx'), ('Text file', 'txt'),
    ('Rich-text format', 'rtf')
]


#: A list of tuples that define the types of user-uploaded files that are supported for an instance of the
# WholesaleImport model. Each tuple has two items: the first is a user-friendly short description of the supported file
# type; the second is the expected extension of the supported file type.
CONST_SUPPORTED_WHOLESALE_FILE_TYPES = [('Comma-separated value file', 'csv')]


#: A list of tuples that define the types of user-uploaded files that are supported for an instance of the Attachment
# model. Each tuple has two items: the first is a user-friendly short description of the supported file type; the second
# is the expected extension of the supported file type.
CONST_SUPPORTED_ATTACHMENT_FILE_TYPES = [
    ('Adobe PDF', 'pdf'), ('Microsoft Word 97-2003', 'doc'), ('Microsoft Word 2007+', 'docx'), ('Text file', 'txt'),
    ('Rich-text format', 'rtf'), ('JPG image file', 'jpg'), ('JPEG image file', 'jpeg'), ('PNG image file', 'png'),
    ('GIF image file', 'gif'), ('BMP image file', 'bmp'), ('TIFF image file', 'tiff'), ('TIF image file', 'tif'),
    ('Microsoft Excel 97-2003', 'xls'), ('Microsoft Excel 2007+', 'xlsx'), ('Comma-separated value file', 'csv'),
    ('Microsoft PowerPoint 97-2003', 'ppt'), ('Microsoft PowerPoint 2007+', 'pptx'),
    ('Apple Quicktime video file', 'mov'), ('MPEG-4 video file', 'mp4'), ('Open Web Media file', 'webm'),
]

#: A list of tuples that define the types of user-uploaded files that are supported for an instance of the Person Photo
# model. Each tuple has two items: the first is a user-friendly short description of the supported file type; the second
# is the expected extension of the supported file type.
CONST_SUPPORTED_PERSON_PHOTO_FILE_TYPES = [
    ('JPG image file', 'jpg'), ('JPEG image file', 'jpeg'), ('PNG image file', 'png'),
    ('GIF image file', 'gif'), ('BMP image file', 'bmp'), ('TIFF image file', 'tiff'), ('TIF image file', 'tif')
]


#: A list of names of models that are whitelisted for use through the wholesale import tool.
CONST_WHOLESALE_WHITELISTED_MODELS = [
    # From the 'sourcing' app
    'Attachment',
    'Content',
    'ContentIdentifier',
    'ContentCase',
    'ContentPerson',
    'ContentPersonAllegation',
    'ContentPersonPenalty',
    # From the 'core' app
    'Person',
    'PersonContent',
    'PersonAlias',
    'PersonPhoto',
    'PersonIdentifier',
    'PersonTitle',
    'PersonRelationship',
    'PersonPayment',
    'Grouping',
    'GroupingAlias',
    'GroupingRelationship',
    'PersonGrouping',
    'Incident',
    'PersonIncident',
    'GroupingIncident',
    # From the 'supporting' app
    'State',
    'County',
    'Location',
    'Court',
]


#: A list of names of fields that are blacklisted from use through the wholesale import tool.
CONST_WHOLESALE_BLACKLISTED_FIELDS = []
