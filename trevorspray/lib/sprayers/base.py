import requests
from ..errors import TREVORSprayError

class BaseSprayModule:

    # HTTP method
    method = 'POST'
    # default target URL
    default_url = None
    # name of username parameter
    userparam = 'username'
    # name of password parameter
    passparam = 'password'
    # other parameters
    miscparams = {}
    # body of request
    body = {}
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

    def initialize(self):
        return True


    def create_request(self, username, password):
        '''
        Returns request.Request() object
        '''

        if type(self.body) == dict:
            data = dict(self.body)
            data.update({
                self.userparam: username,
                self.passparam: password
            })
            data.update(self.miscparams)
        else:
            data = str(self.body.format(
                username=username,
                password=password,
                **self.miscparams
            ))
        return requests.Request(
            method=self.method,
            url=self.url,
            headers=self.headers,
            cookies=self.cookies,
            data=data
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