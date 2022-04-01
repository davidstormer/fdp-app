from social_core.exceptions import AuthForbidden
import logging

logger = logging.getLogger(__name__)


def auth_allowed(backend, details, response, *args, **kwargs):
    if not backend.auth_allowed(response, details):
        logger.error(f"AUDIT | Failed login: email \"{details.get('email')}\" domain not found in "
                     f"FDP_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_WHITELISTED_DOMAINS. Response UPN: "
                     f"\"{response.get('upn')}\"")
        raise AuthForbidden(backend)
