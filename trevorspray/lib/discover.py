import re
import json
import logging
import requests
import dns.resolver
from contextlib import suppress
from .util import highlight_json

log = logging.getLogger('trevorspray.discovery')

suggestion_regexes = (
    re.compile(r'[^\d\W_-]+', re.I),
    re.compile(r'[^\W_-]+', re.I),
    re.compile(r'[^\d\W]+', re.I),
    re.compile(r'[^\W]+', re.I),
)

class DomainDiscovery:

    def __init__(self, domain):

        self.domain = ''.join(str(domain).split()).strip('/')


    def recon(self):

        self.printjson(self.mxrecords())
        self.printjson(self.txtrecords())
        self.printjson(self.openid_configuration())
        self.printjson(self.getuserrealm())
        self.printjson(self.autodiscover())


    @staticmethod
    def printjson(j):

        if j:
            log.success(f'\n{highlight_json(j)}')
        else:
            log.warn('No results.')

    def openid_configuration(self):

        url = f'https://login.windows.net/{self.domain}/.well-known/openid-configuration'
        log.info(f'Checking OpenID configuration at {url}')
        log.info(f'NOTE: You can spray against "token_endpoint" with --url!!')

        content = dict()
        with suppress(Exception):
            content = requests.get(url).json()

        return content


    def getuserrealm(self):

        url = f'https://login.microsoftonline.com/getuserrealm.srf?login=test@{self.domain}'
        log.info(f'Checking user realm at {url}')

        content = dict()
        with suppress(Exception):
            content = requests.get(url).json()

        return content


    def mxrecords(self):
        
        log.info(f'Checking MX records for {self.domain}')
        mx_records = []
        with suppress(Exception):
            for x in dns.resolver.query(self.domain, 'MX'):
                mx_records.append(x.to_text())
        return mx_records


    def txtrecords(self):
        
        log.info(f'Checking TXT records for {self.domain}')
        txt_records = []
        with suppress(Exception):
            for x in dns.resolver.query(self.domain, 'TXT'):
                txt_records.append(x.to_text())
        return txt_records


    def autodiscover(self):

        url = f'https://outlook.office365.com/autodiscover/autodiscover.json/v1.0/test@{self.domain}?Protocol=Autodiscoverv1'
        log.info(f'Checking autodiscover info at {url}')

        content = dict()
        with suppress(Exception):
            content = requests.get(url).json()

        return content


    def suggest(self):

        import wordninja
        import tldextract

        domain_info = tldextract.extract(self.domain)
        domain = '.'.join([domain_info.subdomain, domain_info.domain])

        suggestions = set()
        for r in suggestion_regexes:
            matches = r.findall(domain)
            suggestions.add(''.join(matches))
            for match in matches:
                suggestions.add(match)

        wn = wordninja.split(domain)
        if len(wn) >= 3:
            with suppress(Exception):
                suggestions.add(''.join(_[0] for _ in wn))
        for match in wn:
            suggestions.add(match)

        wn = wordninja.split(self.domain)
        for length in range(1, len(wn) + 1):
            iterations = (len(wn) + 1) - length
            for i in range(iterations):
                suggestions.add(''.join(wn[i:i+length]))

        suggestions = list(f'{s}.onmicrosoft.com' for s in suggestions)

        return sorted(list(suggestions), key=lambda x: len(x))
