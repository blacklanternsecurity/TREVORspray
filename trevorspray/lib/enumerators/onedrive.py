import logging
from ..util import request
from ..sprayers.base import BaseSprayModule

log = logging.getLogger("trevorspray.enumerators.onedrive")


class OneDriveUserEnum(BaseSprayModule):
    # HTTP method
    method = "GET"
    # default target URL
    default_url = "https://{tenantname}-my.sharepoint.com/personal/{username}_{domain}/_layouts/15/onedrive.aspx"
    # How many times to retry HTTP requests
    retries = 0

    def initialize(self):
        # determine domain
        self.domain = self.trevor.runtimeparams.get("domain", "")
        if not self.domain:
            self.domain = str(self.trevor.domain)
            if not self.domain:
                log.error(
                    "Failed to determine domain. Please set the environment variable: TREVOR_domain=<domain>"
                )
                return False
            log.info(
                f'Using domain "{self.domain}" (export TREVOR_domain=<domain> to override)'
            )

        # determine tenant name
        self.discovery = self.trevor.discovery(self.domain)
        self.tenantname = self.trevor.env.get("tenantname", "")
        if not self.tenantname:
            if self.discovery.onedrive_tenantnames():
                self.tenantname = self.discovery.onedrive_tenantnames()[0]
                log.info(
                    f'Using tenantname "{self.tenantname}" (export TREVOR_tenantname=<tenantname> to override)'
                )
            else:
                log.error(
                    "Failed to confirm tenant name via OneDrive. To force, set the environment variable: TREVOR_tenantname=<tenantname>"
                )
                return False

        self.globalparams.update(
            {
                "domain": self.domain.replace(".", "_").replace("-", "_"),
                "tenantname": self.tenantname,
            }
        )

        return True

    def create_params(self, username, password):
        user = str(username).split("@")[0].replace(".", "_").replace("-", "_")
        return {
            "username": user,
        }

    def check_response(self, response):
        valid = None
        exists = False
        locked = None

        status_code = getattr(response, "status_code", 0)
        msg = f'Response code "{status_code}"'

        if response.status_code in [200, 401, 403, 302]:
            msg = f'Confirmed valid user via OneDrive! (Response code "{status_code}")'
            exists = True

        return (valid, exists, locked, msg)
