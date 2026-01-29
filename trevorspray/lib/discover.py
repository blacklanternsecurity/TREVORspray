import re
import logging
import dns.resolver
from .util import *
from contextlib import suppress
from urllib.parse import urlparse, urlunparse
from pathlib import Path

log = logging.getLogger("trevorspray.discovery")

suggestion_regexes = (
    re.compile(r"[^\d\W_-]+", re.I),
    re.compile(r"[^\W_-]+", re.I),
    re.compile(r"[^\d\W]+", re.I),
    re.compile(r"[^\W]+", re.I),
)


class DomainDiscovery:
    def __init__(self, trevor, domain):
        self.trevor = trevor
        self.domain = "".join(str(domain).split()).strip("/")

        self._mxrecords = None
        self._txtrecords = None
        self._autodiscover = None
        self._userrealm = None
        self._openid_configuration = None
        self._msoldomains = None
        self._owa = None
        self._onedrive_tenantnames = None
        self.tenantnames = []

    def recon(self):
        self.printjson(self.mxrecords())
        self.printjson(self.txtrecords())

        openid_configuration = self.openid_configuration()
        self.printjson(openid_configuration)
        authorization_endpoint = openid_configuration.get("authorization_endpoint", "")
        uuid_regex = re.compile(
            r"[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}"
        )
        matches = uuid_regex.findall(authorization_endpoint)
        if matches:
            log.success(f'Tenant ID: "{matches[0]}"')

        self.printjson(self.getuserrealm())
        self.printjson(self.autodiscover())
        
        if not self.trevor.options.skip_owa:
            self.owa()
        else:
            log.info("Skipping OWA discovery")

        msoldomains = self.msoldomains()
        if msoldomains:
            self.printjson(msoldomains)
            loot_dir = self.trevor.home / "loot"
            loot_file = loot_dir / f"recon_{self.domain}_other_tenant_domains.txt"
            update_file(loot_file, msoldomains)
            log.info(f"Wrote {len(msoldomains):,} domains to {loot_file}")
            
            if self.trevor.options.export_tenants:
                filtered_domains = [d for d in msoldomains if 'onmicrosoft.com' not in d.lower()]
                export_file = Path(self.trevor.options.export_tenants)
                export_file.parent.mkdir(parents=True, exist_ok=True)
                with open(export_file, 'w') as f:
                    for domain in filtered_domains:
                        f.write(f"{domain}\n")
                log.success(f"Exported {len(filtered_domains)} domains to {export_file}")
        
        self.onedrive_tenantnames()

    @staticmethod
    def printjson(j):
        if j:
            log.success(f"\n{highlight_json(j)}")
        else:
            log.warn("No results.")

    def openid_configuration(self):
        if self._openid_configuration is None:
            url = f"https://login.windows.net/{self.domain}/.well-known/openid-configuration"
            log.info(f"Checking OpenID configuration at {url}")
            log.info(f'NOTE: You can spray against "token_endpoint" with --url!!')

            content = dict()
            with suppress(Exception):
                content = request(url=url).json()
            self._openid_configuration = content

        return self._openid_configuration

    def getuserrealm(self):
        if self._userrealm is None:
            url = f"https://login.microsoftonline.com/getuserrealm.srf?login=test@{self.domain}"
            log.info(f"Checking user realm at {url}")

            content = dict()
            with suppress(Exception):
                content = request(url=url).json()
            self._userrealm = content

        return self._userrealm

    def mxrecords(self):
        if self._mxrecords is None:
            log.info(f"Checking MX records for {self.domain}")
            mx_records = []
            with suppress(Exception):
                for x in dns.resolver.query(self.domain, "MX"):
                    mx_records.append(x.to_text())
            self._mxrecords = mx_records

        return self._mxrecords

    def txtrecords(self):
        if self._txtrecords is None:
            log.info(f"Checking TXT records for {self.domain}")
            txt_records = []
            with suppress(Exception):
                for x in dns.resolver.query(self.domain, "TXT"):
                    txt_records.append(x.to_text())
            self._txtrecords = txt_records

        return self._txtrecords

    def autodiscover(self):
        if self._autodiscover is None:
            url = f"https://outlook.office365.com/autodiscover/autodiscover.json/v1.0/test@{self.domain}?Protocol=Autodiscoverv1"
            log.info(f"Checking autodiscover info at {url}")

            content = dict()
            with suppress(Exception):
                content = request(url=url, retries=0).json()
            self._autodiscover = content

        return self._autodiscover

    def msoldomains(self):
        if self._msoldomains is None:
            url = f"https://azmap.dev/api/tenant?domain={self.domain}&extract=true"
            log.info(f"Retrieving tenant domains at {url}")

            domains = []
            with suppress(Exception):
                response = request(url=url)
                data = response.json()

                tenant_name = data.get("tenant_name", "")
                if tenant_name:
                    self.tenantnames.append(tenant_name)

                domains = data.get("email_domains", [])

            if self.tenantnames:
                log.success(f'Found tenant names: "{", ".join(self.tenantnames)}"')

            if domains:
                log.success(f"Found {len(domains):,} domains under tenant!")

            self._msoldomains = domains

        return self._msoldomains

    def onedrive_tenantnames(self):
        if self._onedrive_tenantnames is None:
            self.msoldomains()

            if not self.tenantnames:
                return []

            self._onedrive_tenantnames = []

            log.info(f"Checking OneDrive instances")

            tenantname_override = self.trevor.runtimeparams.get("tenantname", "")
            for tenantname in (
                [tenantname_override] if tenantname_override else self.tenantnames
            ):
                url = f'https://{tenantname}-my.sharepoint.com/personal/TESTUSER_{"_".join(self.domain.split("."))}/_layouts/15/onedrive.aspx'

                status_code = 0
                with suppress(Exception):
                    status_code = request(url=url, method="HEAD", retries=0).status_code

                if status_code:
                    log.success(f'Tenant "{tenantname}" confirmed via OneDrive: {url}')
                    self._onedrive_tenantnames.append(tenantname)
                else:
                    log.warning(
                        f'Hosted OneDrive instance for "{tenantname}" does not exist'
                    )
            self._onedrive_tenantnames = list(set(self._onedrive_tenantnames))

        return self._onedrive_tenantnames

    def owa(self):
        if self._owa is None:
            log.info("Attempting to discover OWA instances")

            owas = set()

            schemes = ["http://", "https://"]

            urls = [
                f"autodiscover.{self.domain}/autodiscover/autodiscover.xml",
                f"exchange.{self.domain}/autodiscover/autodiscover.xml",
                f"webmail.{self.domain}/autodiscover/autodiscover.xml",
                f"email.{self.domain}/autodiscover/autodiscover.xml",
                f"mail.{self.domain}/autodiscover/autodiscover.xml",
                f"owa.{self.domain}/autodiscover/autodiscover.xml",
                f"mx.{self.domain}/autodiscover/autodiscover.xml",
                f"{self.domain}/autodiscover/autodiscover.xml",
            ]
            urls += [
                f'{mx.split()[-1].strip(".")}/autodiscover/autodiscover.xml'
                for mx in self.mxrecords()
            ]
            if self.trevor.options.url:
                parsed_url = urlparse(self.trevor.options.url)
                base_url = urlunparse(parsed_url._replace(query="", path=""))
                urls += [f"{base_url}/autodiscover/autodiscover.xml"]
            urls = list(set(urls))

            headers = {"Content-Type": "text/xml"}

            with ThreadPool(maxthreads=10) as pool:
                pool.start()
                for scheme in schemes:
                    for u in urls:
                        url = f"{scheme}{u}"
                        pool.submit(request, url=url, headers=headers, retries=0)
                for r in pool.results(wait=True):
                    response_headers = {
                        k.lower(): v for k, v in getattr(r, "headers", {}).items()
                    }
                    if (
                        r is not None
                        and type(r) != str
                        and (
                            "x-owa-version" in response_headers
                            or "NTLM" in response_headers.get("www-authenticate", "")
                        )
                    ):
                        log.success(f"Found OWA at {r.request.url}")
                        pool.submit(self.owa_internal_domain, url=r.request.url)
                        owas.add(r.request.url)

            self._owa = list(owas)

        return self._owa

    def owa_internal_domain(self, url=None):
        """
        Stolen from:
            - https://github.com/dafthack/MailSniper
            - https://github.com/rapid7/metasploit-framework/blob/master/modules/auxiliary/scanner/http/owa_login.rb
        """

        if url is None:
            url = f"https://{self.trevor.domain}/autodiscover/autodiscover.xml"

        log.debug(f"Trying to extract internal domain via NTLM from {url}")

        juicy_endpoints = [
            "aspnet_client",
            "autodiscover",
            "autodiscover/autodiscover.xml",
            "ecp",
            "ews",
            "ews/exchange.asmx",
            "ews/services.wsdl",
            "exchange",
            "microsoft-server-activesync",
            "microsoft-server-activesync/default.eas",
            "oab",
            "owa",
            "powershell",
            "rpc",
        ]

        urls = {
            url,
        }
        parsed_url = urlparse(url)
        base_url = urlunparse(parsed_url._replace(query="", path=""))
        for endpoint in juicy_endpoints:
            urls.add(f"{base_url}/{endpoint}".lower())

        netbios_domain = ""
        for url in urls:
            r = request(
                "POST",
                url,
                headers={
                    "Authorization": "NTLM TlRMTVNTUAABAAAAB4IIogAAAAAAAAAAAAAAAAAAAAAGAbEdAAAADw=="
                },
                timeout=3,
            )
            ntlm_info = {}
            www_auth = getattr(r, "headers", {}).get("WWW-Authenticate", "")
            if www_auth:
                try:
                    ntlm_info = ntlmdecode(www_auth)
                except Exception as e:
                    log.debug(f"Failed to extract NTLM domain: {e}")
            if ntlm_info:
                netbios_domain = ntlm_info.get(
                    "DNS_Domain_name",
                    ntlm_info.get(
                        "DNS_Tree_Name", ntlm_info.get("NetBIOS_Domain_Name", "")
                    ),
                )
                log.success(f'Found internal domain via NTLM: "{netbios_domain}"')
                ntlm_info.pop("Timestamp", "")
                self.printjson(ntlm_info)
                break
        return netbios_domain
