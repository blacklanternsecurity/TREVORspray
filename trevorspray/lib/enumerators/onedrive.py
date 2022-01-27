import logging
from ..util import request
from ..sprayers.base import BaseSprayModule

log = logging.getLogger('trevorspray.enumerators.onedrive')

class OneDriveUserEnum(BaseSprayModule):

    # HTTP method
    method = 'GET'
    # default target URL
    default_url = 'https://{tenantname}-my.sharepoint.com/personal/{username}_{domain}/_layouts/15/onedrive.aspx'

    def initialize(self):

        self.globalparams.update({
            'domain': '_'.join(self.trevor.discovery.domain.split('.'))
        })

        if self.trevor.discovery and self.trevor.discovery.confirmed_tenantnames:
            tenantname = self.trevor.discovery.confirmed_tenantnames[0]
            log.verbose(f'Using first tenantname "{tenantname}" (export TREVOR_tenantname=<tenantname> to override)')
            self.globalparams.update({
                'tenantname': tenantname
            })
        else:
            log.error('OneDrive user enumation: failed to determine tenant name')
            return False

        return True


    def create_params(self, username, password):

        user = str(username).split('@')[0].replace('.', '_').replace('-', '_')
        return {
            'username': user,
        }


    def check_response(self, response):

        valid = None
        exists = False
        locked = None
        msg = f'Response code "{response.status_code}"'

        if response.status_code in [200, 401, 403, 302]:
            msg = f'Confirmed valid user via OneDrive! (Response code "{response.status_code}")'
            exists = True

        return (valid, exists, locked, msg)