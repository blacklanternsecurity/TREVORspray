import logging
import requests
from time import sleep
from urllib.parse import quote
from ..util import windows_user_agent
from ..errors import TREVORSprayError

log = logging.getLogger("trevorspray.sprayers.base")


class BaseSprayModule:
    # HTTP method
    method = "POST"
    # default target URL
    default_url = None
    # alternative IPv6 URL
    ipv6_url = None
    # name of username parameter
    userparam = "username"
    # name of password parameter
    passparam = "password"
    # other global parameters
    globalparams = {}
    # body of request
    request_data = None
    request_json = None
    # HTTP headers
    headers = {}
    # HTTP cookies
    cookies = {}
    # Don't count nonexistent accounts as failed logons
    fail_nonexistent = True
    # Module for looting after successful login
    looter = None
    # How many times to retry HTTP requests
    retries = "infinite"

    def __init__(self, trevor):
        log.debug(f"Initializing sprayer")

        self.url = None
        self.trevor = trevor
        if self.trevor.options.url is not None:
            self.url = str(self.trevor.options.url)
        elif self.default_url is not None:
            self.url = str(self.default_url)

        if (
            self.ipv6_url
            and self.url == self.default_url
            and self.trevor.options.prefer_ipv6
        ):
            self.url = self.ipv6_url

        if not self.url:
            raise TREVORSprayError("Please specify a --url to spray against")

        # make sure we have a user-agent
        if not self.headers.get("User-Agent", ""):
            self.headers["User-Agent"] = windows_user_agent

    def initialize(self):
        return True

    def create_params(self, username, password):
        return {self.userparam: username, self.passparam: password}

    def create_request(self, username, password):
        """
        Returns request.Request() object
        """

        runtimeparams = self.create_params(username, password)

        data = None
        params = dict(self.globalparams)
        params.update(runtimeparams)
        params.update(self.trevor.runtimeparams)

        try:
            url = self.url.format(**params)
        except Exception as e:
            log.error(
                f'Error preparing URL "{self.url}" with the following parameters: {params}: {e} (-v to debug)'
            )
            if log.level <= logging.DEBUG:
                import traceback

                log.error(traceback.format_exc())
            url = str(self.url)
            log.error(
                f'Continuing with URL "{url}". If this doesn\'t look right, press CTRL+C to cancel.'
            )
            sleep(4)

        if not url.lower().startswith("http"):
            url = f"https://{url}"

        if type(self.request_data) == dict:
            data = dict(self.request_data)
            data.update({k: v for k, v in params.items() if k in data})
        elif type(self.request_data) == str:
            escaped_params = {k: quote(v) for k, v in params.items()}
            data = self.request_data.format(**escaped_params)

        json = None
        if type(self.request_json) == dict:
            json = dict(self.request_json)
            json.update({k: v for k, v in params.items() if k in json})

        return requests.Request(
            method=self.method,
            url=url,
            headers=self.headers,
            cookies=self.cookies,
            data=data,
            json=json,
        )

    def check_response(self, response):
        """
        returns (valid, exists, locked, msg)
        """

        valid = False
        exists = None
        locked = None
        msg = ""

        if getattr(response, "status_code", 0) == 200:
            valid = True
            exists = True
            msg = "Valid cred"

        return (valid, exists, locked, msg)

    def loot(self, credential):
        if self.looter is not None:
            looter = self.looter(self, credential)
            looter.run()

    @property
    def id(self):
        return f"{self.__class__.__name__}|{self.url}"
