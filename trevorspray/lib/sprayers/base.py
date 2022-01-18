import os
import requests
from urllib.parse import quote
from ..util import windows_user_agent
from ..errors import TREVORSprayError

class BaseSprayModule:

    # HTTP method
    method = 'POST'
    # default target URL
    default_url = None
    # alternative IPv6 URL
    ipv6_url = None
    # name of username parameter
    userparam = 'username'
    # name of password parameter
    passparam = 'password'
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
    fail_nonexistent = False
    # Module for looting after successful login
    looter = None

    def __init__(self, trevor):

        self.trevor = trevor
        if self.trevor.options.url is not None:
            self.url = str(self.trevor.options.url)
        elif self.default_url is not None:
            self.url = str(self.default_url)
        else:
            raise TREVORSprayError('Please specify a --url to spray against')

        if self.ipv6_url and self.url == self.default_url and self.trevor.options.prefer_ipv6:
            self.url = self.ipv6_url

        # enumerate environment variables
        self.runtimeparams = {}
        keyword = 'TREVOR_'
        for k,v in os.environ.items():
            if k.startswith(keyword):
                _k = k.split(keyword)[-1]
                self.runtimeparams[_k] = v

        # make sure we have a user-agent
        if not self.headers.get('User-Agent', ''):
            self.headers['User-Agent'] = windows_user_agent


    def initialize(self):
        return True


    def create_request(self, username, password):
        '''
        Returns request.Request() object
        '''

        runtimeparams = {
            self.userparam: username,
            self.passparam: password
        }
        runtimeparams.update(self.runtimeparams)

        url = self.url.format(**self.globalparams, **runtimeparams)
        if not url.lower().startswith('http'):
            url = f'https://{url}'

        data = None
        params = dict(self.globalparams)
        params.update(runtimeparams)
        if type(self.request_data) == dict:
            data = dict(self.request_data)
            data.update(params)
        elif type(self.request_data) == str:
            params = {k: quote(v) for k,v in params.items()}
            data = self.request_data.format(**params)

        json = None
        if type(self.request_json) == dict:
            json = dict(self.request_json)
            json.update(params)

        return requests.Request(
            method=self.method,
            url=url,
            headers=self.headers,
            cookies=self.cookies,
            data=data,
            json=json
        )


    def check_response(self, response):
        '''
        returns (valid, exists, locked, msg)
        '''

        valid = False
        exists = None
        locked = None
        msg = ''

        if getattr(response, 'status_code', 0) == 200:
            valid = True
            exists = True
            msg = 'Valid cred'

        return (valid, exists, locked, msg)


    def loot(self, credential):

        if self.looter is not None:
            looter = self.looter(self, credential)
            looter.run()


    @property
    def id(self):

        return f'{self.__class__.__name__}|{self.url}'