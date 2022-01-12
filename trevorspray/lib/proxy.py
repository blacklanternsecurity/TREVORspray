import random
import logging
import requests
import threading
from time import sleep
from contextlib import suppress
from .util import windows_user_agent
from trevorproxy.lib.ssh import SSHProxy
from trevorproxy.lib.errors import SSHProxyError

log = logging.getLogger('trevorspray.proxy')


class SubnetThread(threading.Thread):

    def __init__(self, *args, **kwargs):

        self.listen_address = '127.0.0.1'
        self.trevor = kwargs.pop('trevor', None)

        super().__init__(*args, **kwargs)

    def run(self):

        from trevorproxy.lib.subnet import SubnetProxy
        from trevorproxy.lib.socks import ThreadingTCPServer, SocksProxy

        subnet_proxy = SubnetProxy(
            interface=self.trevor.options.interface,
            subnet=self.trevor.options.subnet
        )
        try:
            subnet_proxy.start()
            with ThreadingTCPServer(
                    (self.listen_address, self.trevor.options.base_port),
                    SocksProxy,
                    proxy=subnet_proxy,
                ) as server:
                log.info(f'Listening on socks5://{self.listen_address}:{self.trevor.options.base_port}')
                server.serve_forever()
        finally:
            subnet_proxy.stop()


class ProxyThread(threading.Thread):

    def __init__(self, *args, **kwargs):

        self.trevor = kwargs.pop('trevor', None)
        host = kwargs.pop('host', None)
        proxy_port = kwargs.pop('proxy_port', None)

        self.proxy = None
        self.proxy_arg = None

        if host == '<subnet>':
            self.proxy = str(self.trevor.options.subnet)
            self.proxy_arg = {
                'http': f'socks5://{self.trevor.subnet_proxy.listen_address}:{self.trevor.options.base_port}',
                'https': f'socks5://{self.trevor.subnet_proxy.listen_address}:{self.trevor.options.base_port}',
            }

        elif host is not None:
            self.proxy = SSHProxy(
                host=host,
                key=self.trevor.options.key,
                key_pass=self.trevor.options.key_pass,
                proxy_port=proxy_port,
            )
            self.proxy.start()
            self.proxy_arg = {
                'http': str(self.proxy),
                'https': str(self.proxy)
            }

        super().__init__(*args, **kwargs)
        self._running = False
        self.lock = threading.Lock()
        self.q = None


    def stop(self):

        with suppress(Exception):
            self.proxy.stop()


    def submit(self, user, password):

        with self.lock:
            if self.q is None:
                self.q = (user, password)
                return True
        return False


    def run(self):

        while not self.trevor._stop:

            try:

                user, password = None, None
                with self.lock:
                    if self.q is not None:
                        user, password = self.q
                        self.q = None

                login_id = f'{self.trevor.sprayer.id}|{user}|{password}'

                if not user:
                    sleep(.1)
                    continue

                self._running = True

                with self.trevor.lock:
                    self.trevor.sprayed_counter += 1
                    if login_id in self.trevor.tried_logins:
                        log.info(f'Already tried {user}:{password}, skipping.')
                        self._running = False
                        continue

                valid, exists, locked, msg = self.check_cred(user, password)

                with self.trevor.lock:
                    self.trevor.tried_logins[login_id] = True

                    if valid:
                        exists = True
                        log.success(f'{user}:{password} - {msg}')
                        self.trevor.valid_logins.append(f'{user}:{password}')
                        if self.trevor.options.exit_on_success:
                            self.trevor._stop = True
                    elif locked:
                        log.error(f'{user}:{password} - {msg}')
                    elif exists:
                        log.warning(f'{user}:{password} - {msg}')
                    else:
                        log.info(f'{user}:{password} - {msg}')

                    if exists:
                        self.trevor.existent_users.append(user)

                    if locked:
                        self.trevor.lockout_counter += 1

                    if valid:
                        if not self.trevor.options.no_loot:
                            self.trevor.sprayer.loot((user, password))
                        if self.trevor.options.exit_on_success:
                            self._running = False
                            self.q = None
                            return

                    # If the force flag isn't set and lockout count is 10 we'll ask if the user is sure they want to keep spraying
                    if not self.trevor.options.force and self.trevor.lockout_counter == 10 and self.trevor.lockout_question == False:
                        log.error('Multiple Account Lockouts Detected!')
                        log.error('10 of the accounts you sprayed appear to be locked out. Do you want to continue this spray?')
                        yes = {'yes', 'y'}
                        no = {'no', 'n', ''}
                        self.trevor.lockout_question = True
                        choice = 'X'
                        while (choice not in no and choice not in yes):
                            choice = input('[USER] [Y/N] (default is N): ').lower()

                        if choice in no:
                            log.info('Cancelling the password spray.')
                            log.info('NOTE: If you are seeing multiple "account is locked" messages after your first 10 attempts or so this may indicate Azure AD Smart Lockout is enabled.')
                            return self.cancel_spray()

                print(f'       Sprayed {self.trevor.sprayed_counter:,} / {self.trevor.sprayed_possible:,} accounts\r', end='', flush=True)

                if locked and self.trevor.options.lockout_delay:
                    log.verbose(f'Lockout encountered, sleeping thread for {self.trevor.options.lockout_delay:.1f} seconds')
                    sleep(self.trevor.options.lockout_delay)

                if (self.trevor.options.delay or self.trevor.options.jitter) and (exists or locked or self.trevor.sprayer.fail_nonexistent):
                    delay = float(self.trevor.options.delay)
                    jitter = random.random() * self.trevor.options.jitter
                    delay += jitter
                    if delay > 0:
                        if self.trevor.options.ssh:
                            log.debug(f'Sleeping thread for {delay:.1f} seconds ({self.trevor.options.delay:.1f}s delay + {jitter:.1f}s jitter)')
                            sleep(delay)
                        else:
                            log.debug(f'Sleeping for {delay:.1f} seconds ({self.trevor.options.delay:.1f}s delay + {jitter:.1f}s jitter)')
                            with self.trevor.lock:
                                sleep(delay)

                self._running = False

            except Exception as e:
                log.error(f'Unhandled error in proxy thread: {e}')
                if log.level <= logging.DEBUG:
                    import traceback
                    log.error(traceback.format_exc())
                else:
                    log.error(f'Encountered error (-v to debug): {e}')
                self.cancel_spray()
                break


    def cancel_spray(self):

        self.trevor._stop = True
        self._running = False
        self.q = None


    @property
    def running(self):

        return self._running or self.q is not None
    

    def check_cred(self, user, password):

        result = None
        while result is None:
            try:
                session = requests.Session()
                try:
                    request = self.trevor.sprayer.create_request(user, password).prepare()
                except Exception as e:
                    log.error(f'Unhandled error in {self.trevor.sprayer.__class__.__name__}.create_request(): {e}')
                    if log.level <= logging.DEBUG:
                        import traceback
                        log.error(traceback.format_exc())
                    self.trevor._stop = True
                    self._running = False
                    break

                # randomize user-agent if requested
                if self.trevor.options.random_useragent:
                    current_useragent = request.headers.get('User-Agent', windows_user_agent)
                    request.headers['User-Agent'] = f'{current_useragent} {random.randint(0,99999)}.{random.randint(0,99999)}'

                log.debug(f'Requesting {request.method} {request.url} through proxy: {self.proxy}')
                kwargs = {
                    'timeout': self.trevor.options.timeout,
                    'allow_redirects': False,
                    'verify': False
                }
                if self.trevor.options.proxy:
                    kwargs['proxies'] = {
                        'http': self.trevor.options.proxy,
                        'https': self.trevor.options.proxy
                    }
                if self.proxy is not None:
                    kwargs['proxies'] = self.proxy_arg
                response = session.send(
                    request,
                    **kwargs
                )
                log.debug(f'Finished requesting {request.url} through proxy: {self.proxy}')
                try:
                    result = self.trevor.sprayer.check_response(response)
                except Exception as e:
                    log.error(f'Unhandled error in {self.trevor.sprayer.__class__.__name__}.check_response(): {e}')
                    if log.level <= logging.DEBUG:
                        import traceback
                        log.error(traceback.format_exc())

            except requests.exceptions.RequestException as e:
                log.error(f'Error in request: {e}')
                log.error('Retrying...')
                # rebuild proxy
                if self.proxy_arg and not type(self.proxy) == str:
                    try:
                        self.proxy.start()
                    except SSHProxyError as e:
                        log.error(e)
                sleep(1)
        return result
