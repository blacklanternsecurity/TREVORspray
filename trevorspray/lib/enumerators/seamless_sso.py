import logging
from contextlib import suppress
from ..sprayers.base import BaseSprayModule

log = logging.getLogger("trevorspray.enumerators.seamless_sso")


class SeamlessSSO(BaseSprayModule):
    # HTTP method
    method = "POST"
    # default target URL
    default_url = "https://login.microsoftonline.com/common/GetCredentialType"
    # body of request
    request_json = {
        "username": "{username}",
        "isOtherIdpSupported": "true",
        "checkPhones": "true",
        "isRemoteNGCSupported": "false",
        "isCookieBannerShown": "false",
        "isFidoSupported": "false",
        "originalRequest": "",
    }
    # HTTP headers
    headers = {"Content-Type": "application/json"}
    # How many times to retry HTTP requests
    retries = 0

    def initialize(self):
        log.warning("Enumerating users via the SeamlessSSO method is unreliable.")
        log.warning(
            "After a large number of requests, Microsoft will detect enumeration and begin feeding you false results."
        )
        return True

    def create_params(self, username, password):
        return {"username": username}

    def check_response(self, response):
        valid = None
        exists = False
        locked = None

        status_code = getattr(response, "status_code", 0)
        msg = f'Response code "{status_code}"'

        r = {}
        with suppress(Exception):
            r = response.json()

        existsResult = r.get("IfExistsResult", -1)

        if existsResult in [1]:
            msg = f"Account does not exist (IfExistsResult = {existsResult})"
            exists = False
        elif existsResult in [0, 5, 6]:
            msg = f"Confirmed valid user via SeamlessSSO! (IfExistsResult = {existsResult})"
            exists = True
        elif existsResult != -1:
            msg = f'Got unknown result for IfExistsResult: "{existsResult}")'

        return (valid, exists, locked, msg)
