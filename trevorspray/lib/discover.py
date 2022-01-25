import re
import json
import socket
import logging
import requests
import dns.resolver
from .util import *
import concurrent.futures
from contextlib import suppress
from .enumerators.onedrive import OneDriveUserEnum

log = logging.getLogger('trevorspray.discovery')

suggestion_regexes = (
    re.compile(r'[^\d\W_-]+', re.I),
    re.compile(r'[^\W_-]+', re.I),
    re.compile(r'[^\d\W]+', re.I),
    re.compile(r'[^\W]+', re.I),
)

class DomainDiscovery:

    def __init__(self, trevor, domain):

        self.trevor = trevor
        self.domain = ''.join(str(domain).split()).strip('/')

        self.mx_records = None
        self.txt_records = None
        self.tenantnames = []
        self.confirmed_tenantnames = []


    def recon(self):

        self.printjson(self.mxrecords())
        self.printjson(self.txtrecords())

        openid_configuration = self.openid_configuration()
        self.printjson(openid_configuration)
        authorization_endpoint = openid_configuration.get('authorization_endpoint', '')
        uuid_regex = re.compile(r'[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}')
        matches = uuid_regex.findall(authorization_endpoint)
        if matches:
            log.success(f'Tenant ID: "{matches[0]}"')

        self.printjson(self.getuserrealm())
        self.printjson(self.autodiscover())

        domains = self.domains()
        if domains:
            self.printjson(domains)
            loot_dir = self.trevor.home / 'loot'
            loot_file = loot_dir / f'recon_{self.domain}_other_tenant_domains.txt'
            update_file(loot_file, domains)
            log.info(f'Wrote {len(domains):,} domains to {loot_file}')
        self.onedrive()

        if self.trevor.options.users:
            self.trevor.user_enumerator = OneDriveUserEnum(trevor=self.trevor)


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
            content = request(url=url).json()

        return content


    def getuserrealm(self):

        url = f'https://login.microsoftonline.com/getuserrealm.srf?login=test@{self.domain}'
        log.info(f'Checking user realm at {url}')

        content = dict()
        with suppress(Exception):
            content = request(url=url).json()

        return content


    def mxrecords(self):
        
        if self.mx_records is None:
            log.info(f'Checking MX records for {self.domain}')
            mx_records = []
            with suppress(Exception):
                for x in dns.resolver.query(self.domain, 'MX'):
                    mx_records.append(x.to_text())
            self.mx_records = mx_records
        else:
            mx_records = self.mx_records
        return mx_records


    def txtrecords(self):

        if self.txt_records is None:
            log.info(f'Checking TXT records for {self.domain}')
            txt_records = []
            with suppress(Exception):
                for x in dns.resolver.query(self.domain, 'TXT'):
                    txt_records.append(x.to_text())
            self.txt_records = txt_records
        else:
            txt_records = self.txt_records
        return txt_records


    def autodiscover(self):

        url = f'https://outlook.office365.com/autodiscover/autodiscover.json/v1.0/test@{self.domain}?Protocol=Autodiscoverv1'
        log.info(f'Checking autodiscover info at {url}')

        content = dict()
        with suppress(Exception):
            content = request(url=url).json()

        return content


    def domains(self):

        url = 'https://autodiscover-s.outlook.com/autodiscover/autodiscover.svc'
        #url = 'http://127.0.0.1:8000/autodiscover/autodiscover.svc'

        data = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:exm="http://schemas.microsoft.com/exchange/services/2006/messages" xmlns:ext="http://schemas.microsoft.com/exchange/services/2006/types" xmlns:a="http://www.w3.org/2005/08/addressing" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <soap:Header>
        <a:Action soap:mustUnderstand="1">http://schemas.microsoft.com/exchange/2010/Autodiscover/Autodiscover/GetFederationInformation</a:Action>
        <a:To soap:mustUnderstand="1">https://autodiscover-s.outlook.com/autodiscover/autodiscover.svc</a:To>
        <a:ReplyTo>
            <a:Address>http://www.w3.org/2005/08/addressing/anonymous</a:Address>
        </a:ReplyTo>
    </soap:Header>
    <soap:Body>
        <GetFederationInformationRequestMessage xmlns="http://schemas.microsoft.com/exchange/2010/Autodiscover">
            <Request>
                <Domain>{self.domain}</Domain>
            </Request>
        </GetFederationInformationRequestMessage>
    </soap:Body>
</soap:Envelope>'''

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://schemas.microsoft.com/exchange/2010/Autodiscover/Autodiscover/GetFederationInformation"',
            'User-Agent': 'AutodiscoverClient',
            'Accept-Encoding': 'identity'
        }

        log.info(f'Retrieving tenant domains at {url}')

        response = request(
            'POST',
            url,
            headers=headers,
            data=data
        )

        r = re.compile(r'<Domain>([^<>/]*)</Domain>', re.I)
        domains = list(set(r.findall(response.text)))

        for domain in domains:
            # Check if this is "the initial" domain (tenantname)
            if domain.lower().endswith('.onmicrosoft.com'):
                self.tenantnames.append(domain.split('.')[0])

        if self.tenantnames:
            log.success(f'Found tenant names: "{", ".join(self.tenantnames)}"')

        if domains:
            log.success(f'Found {len(domains):,} domains under tenant!')

        return domains


    def onedrive(self):

        if not self.tenantnames:
            return

        log.info(f'Checking OneDrive instances')

        tenantname_override = self.trevor.runtimeparams.get('tenantname', '')
        for tenantname in ([tenantname_override] if tenantname_override else self.tenantnames):

            url = f'https://{tenantname}-my.sharepoint.com/personal/TESTUSER_{"_".join(self.domain.split("."))}/_layouts/15/onedrive.aspx'

            status_code = 0
            with suppress(Exception):
                status_code = request(
                    url=url,
                    method='HEAD'
                ).status_code

            if status_code:
                log.success(f'Tenant "{tenantname}" confirmed via OneDrive: {url}')
                self.confirmed_tenantnames.append(tenantname)
            else:
                log.warning(f'Hosted OneDrive instance for "{tenantname}" does not exist')

        self.confirmed_tenantnames = list(set(self.confirmed_tenantnames))