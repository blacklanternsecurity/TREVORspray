import requests

class SprayModule:

    # HTTP method
    method = 'POST'
    # name of username parameter
    userparam = 'username'
    # name of password parameter
    passparam = 'password'
    # body of request
    body = {}
    # HTTP headers
    headers = {}
    # HTTP cookies
    cookies = {}
    # Don't count nonexistent accounts as failed logons
    fail_nonexistent = False

    def __init__(self, url):

        self.url = url

    def create_request(self, username, password):
        '''
        Returns request.Request() object
        '''

        data = dict(self.body)
        data.update({
            self.userparam: username,
            self.passparam: password
        })
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
        exists = False
        locked = False
        msg = ''

        if getattr(response, 'status_code', 0) == 200:
            valid = True
            exists = True
            msg = 'Valid cred'

        return (valid, exists, locked, msg)

    @property
    def id(self):

        return f'{self.__class__.__name__}|{self.url}'