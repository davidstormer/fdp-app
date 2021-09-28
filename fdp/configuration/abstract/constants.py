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
    ('Adobe PDF', 'pdf'),
    ('Microsoft Word 97-2003', 'doc'),
    ('Microsoft Word 2007+', 'docx'),
    ('Text file', 'txt'),
    ('Rich-text format', 'rtf'),
    ('JPG image file', 'jpg'),
    ('JPEG image file', 'jpeg'),
    ('PNG image file', 'png'),
    ('GIF image file', 'gif'),
    ('BMP image file', 'bmp'),
    ('TIFF image file', 'tiff'),
    ('TIF image file', 'tif'),
    ('Microsoft Excel 97-2003', 'xls'),
    ('Microsoft Excel 2007+', 'xlsx'),
    ('Comma-separated value file', 'csv'),
    ('text/tab-separated-values', 'tsv'),
    ('Microsoft PowerPoint 97-2003', 'ppt'),
    ('Microsoft PowerPoint 2007+', 'pptx'),
    ('Apple Quicktime video file', 'mov'),
    ('MPEG-4 video file', 'mp4'),
    ('Open Web Media file', 'webm'),
    ('video/x-msvideo', 'avi'),
    ('application/x-dvi', 'dvi'),
    ('video/quicktime', 'qt'),
    ('audio/mpeg', 'mp2'),
    ('audio/mpeg', 'mp3'),
    ('audio/x-wav', 'wav'),
    ('audio/x-aiff', 'aif'),
    ('application/postscript', 'ps'),
    ('application/postscript', 'ai'),
    ('application/postscript', 'eps'),
    ('application/x-pn-realaudio', 'ram'),
    ('application/zip', 'zip'),
    ('audio/basic', 'au'),
    ('audio/basic', 'snd'),
    ('audio/x-aiff', 'aifc'),
    ('audio/x-aiff', 'aiff'),
    ('audio/x-pn-realaudio', 'ra'),
    ('image/ief', 'ief'),
    ('image/svg+xml', 'svg'),
    ('image/x-portable-anymap', 'pnm'),
    ('image/x-portable-bitmap', 'pbm'),
    ('image/x-portable-graymap', 'pgm'),
    ('image/x-portable-pixmap', 'ppm'),
    ('image/x-xbitmap', 'xbm'),
    ('image/x-xpixmap', 'xpm'),
    ('message/rfc822', 'eml'),
    ('message/rfc822', 'mht'),
    ('message/rfc822', 'mhtml'),
    ('message/rfc822', 'nws'),
    ('text/html', 'html'),
    ('text/html', 'htm'),
    ('text/richtext', 'rtx'),
    ('text/x-vcard', 'vcf'),
    ('text/xml', 'xml'),
    ('video/mpeg', 'mpeg'),
    ('video/mpeg', 'm1v'),
    ('video/mpeg', 'mpa'),
    ('video/mpeg', 'mpe'),
    ('video/mpeg', 'mpg'),
    ('video/x-sgi-movie', 'movie')]

#: A list of tuples that define the types of user-uploaded files that are supported for an instance of the Person Photo
# model. Each tuple has two items: the first is a user-friendly short description of the supported file type; the second
# is the expected extension of the supported file type.
CONST_SUPPORTED_PERSON_PHOTO_FILE_TYPES = [
    ('JPG image file', 'jpg'), ('JPEG image file', 'jpeg'), ('PNG image file', 'png'),
    ('GIF image file', 'gif'), ('BMP image file', 'bmp'), ('TIFF image file', 'tiff'), ('TIF image file', 'tif')
]


#: A list of names of models that are in the allowlist for use through the wholesale import tool.
CONST_WHOLESALE_MODELS_ALLOWLIST = [
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


#: A list of names of fields that are excluded from use through the wholesale import tool.
CONST_WHOLESALE_FIELDS_DENYLIST = []
