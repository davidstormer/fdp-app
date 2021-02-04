from django.conf import settings


# FDP system is configured for hosting in Microsoft Azure, so use Azure Storage Account for static and media files
if getattr(settings, 'USE_AZURE_SETTINGS', False):
    from importlib.util import find_spec, module_from_spec

    #: TODO: Defined both here and in base_settings.py. Refactor for a single definition through base_settings.py.
    def load_python_package_module(module_as_str, err_msg, raise_exception):
        """ Dynamically loads a module for a Python package.

        :param module_as_str: Fully qualified module as a string, e.g. my_package.my_module.
        :param err_msg: Exception message if module is not available.
        :param raise_exception: True if an exception should be raised if the module cannot be loaded, False if None should
        be returned.
        :return: Loaded module, or None if raise_exception is False and the module cannot be loaded.
        """
        spec_for_module = find_spec(module_as_str)
        # package for requested module is not installed
        if not spec_for_module:
            # exception should be raised
            if raise_exception:
                raise Exception(err_msg)
            # fail silently
            else:
                return None
        # load module in the package
        module = module_from_spec(spec_for_module)
        # initialize module
        spec_for_module.loader.exec_module(module)
        return module


    # load if django-storage[azure] package is installed
    # see: https://django-storages.readthedocs.io/en/latest/backends/azure.html
    azure_storage_module = load_python_package_module(
        module_as_str='storages.backends.azure_storage',
        err_msg='Please install the package: django-storage[azure]',
        raise_exception=True
    )
    # load if azure-identity package is installed
    # see: https://github.com/Azure/azure-sdk-for-python/tree/master/sdk/identity/azure-identity
    azure_identity_module = load_python_package_module(
        module_as_str='azure.identity',
        err_msg='Please install the package: azure-identity',
        raise_exception=True
    )


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
