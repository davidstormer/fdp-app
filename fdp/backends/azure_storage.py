from django.conf import settings


# FDP system is configured for hosting in Microsoft Azure, so use Azure Storage Account for static and media files
if getattr(settings, 'USE_AZURE_SETTINGS', False):
    from importlib.util import find_spec, module_from_spec
    # check if django-storage[azure] package is installed
    # see: https://django-storages.readthedocs.io/en/latest/backends/azure.html
    azure_storage_spec = find_spec('storages.backends.azure_storage')
    # django-storage[azure] package is not installed
    if not azure_storage_spec:
        raise Exception('Please install the package: django-storage[azure]')
    # load azure_storage module in the django-storage[azure] package
    azure_storage_module = module_from_spec(azure_storage_spec)
    # initialize azure_storage module
    azure_storage_spec.loader.exec_module(azure_storage_module)
    # check if azure-identity package is installed
    # see: https://github.com/Azure/azure-sdk-for-python/tree/master/sdk/identity/azure-identity
    azure_identity_spec = find_spec('azure.identity')
    # azure-identity package is not installed
    if not azure_identity_spec:
        raise Exception('Please install the package: azure-identity')
    # load azure_identity module in the azure_identity package
    azure_identity_module = module_from_spec(azure_identity_spec)
    # initialize azure_identity module
    azure_identity_spec.loader.exec_module(azure_identity_module)


    class MediaAzureStorage(azure_storage_module.AzureStorage):
        """ Defines configuration for storage of user-uploaded media files that are stored in Azure Storage.

        See: https://django-storages.readthedocs.io/en/latest/backends/azure.html

        """
        #: Azure Storage account name
        account_name = settings.AZURE_ACCOUNT_NAME
        #: Azure Storage access key
        account_key = getattr(settings, 'AZURE_ACCOUNT_KEY', None)
        #: Azure Storage user-uploaded media files container
        azure_container = getattr(settings, 'AZURE_MEDIA_CONTAINER', None)
        #: Number of seconds for URL to expire to media file in Azure Storage
        expiration_secs = getattr(settings, 'AZURE_MEDIA_URL_EXPIRATION_SECS', None)
        #: A token credential used to authenticate HTTPS requests. The token value should be updated before its
        # expiration.
        token_credential = azure_identity_module.ManagedIdentityCredential()


    class StaticAzureStorage(azure_storage_module.AzureStorage):
        """ Defines configuration for storage of static files that are stored in Azure Storage.

        See: https://django-storages.readthedocs.io/en/latest/backends/azure.html

        """
        #: Azure Storage account name
        account_name = settings.AZURE_ACCOUNT_NAME
        #: Azure Storage access key
        account_key = getattr(settings, 'AZURE_ACCOUNT_KEY', None)
        #: Azure Storage static files container
        azure_container = getattr(settings, 'AZURE_STATIC_CONTAINER', None)
        #: Number of seconds for URL to expire to static file in Azure Storage
        expiration_secs = getattr(settings, 'AZURE_STATIC_URL_EXPIRATION_SECS', None)


# not expecting to use Azure Storage for either static files or media files, or both
else:

    class MediaAzureStorage:
        """ Empty class since user-uploaded media files are not expected to be stored in Azure Storage.

        """
        pass


    class StaticAzureStorage:
        """ Empty class since static files are not expected to be stored in Azure Storage.

        """
        pass
