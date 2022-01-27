import os
import time
import logging
import importlib
import threading
from . import util
from pathlib import Path
from contextlib import suppress
from .discover import DomainDiscovery
from .proxy import ProxyThread, SubnetThread
from lib.sprayers.base import BaseSprayModule

log = logging.getLogger('trevorspray.sprayer')


class TrevorSpray:

    def __init__(self, options):

        self.options = options
        # enumerate environment variables
        self.runtimeparams = {}
        keyword = 'TREVOR_'
        for k,v in os.environ.items():
            if k.startswith(keyword):
                _k = k.split(keyword)[-1]
                self.runtimeparams[_k] = v

        self.lockout_counter = 0
        self.lockout_question = False

        self.sprayed_counter = 0
        self.sprayed_possible = len(self.options.users) * len(self.options.passwords)

        self.home = Path.home() / '.trevorspray'
        self.home.mkdir(exist_ok=True)

        self.proxies = []
        if options.ssh:
            threads = options.ssh + ([] if options.no_current_ip else [None])
        elif options.subnet:
            threads = ['<subnet>'] * options.threads
        else:
            threads = [None] * options.threads

        self.subnet_proxy = None
        if options.subnet:
            self.subnet_proxy = SubnetThread(
                trevor=self,
                daemon=True
            )
            self.subnet_proxy.start()

        for i,ssh_host in enumerate(threads):
            self.proxies.append(
                ProxyThread(
                    trevor=self,
                    host=ssh_host,
                    proxy_port=options.base_port+i,
                    daemon=True
                )
            )

        self.discovery = None
        self.user_enumerator = None

        spray_modules = importlib.import_module(f'lib.sprayers.{options.module}')
        for m in spray_modules.__dict__.keys():
            spray_module = getattr(spray_modules, m)
            try:
                if BaseSprayModule in spray_module.__bases__:
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
                    self.discovery = DomainDiscovery(self, domain)
                    self.discovery.recon()

            if self.options.users:
                # user enumeration
                if self.options.recon:
                    log.info(f'Enumerating {len(self.options.users):,} users against {self.user_enumerator.url} at {time.ctime()}')
                    self.spray(enumerate_users=True)
                    log.info(f'Enumerated {len(self.existent_users):,} valid users against {self.user_enumerator.url} at {time.ctime()}')
                    self.options.users = list(self.existent_users)

                # password spray
                if self.options.passwords:
                    log.info(f'Spraying {len(self.options.users):,} users * {len(self.options.passwords):,} passwords against {self.sprayer.url} at {time.ctime()}')
                    self.spray()
                    log.info(f'Finished spraying {self.sprayed_counter:,} users against {self.sprayer.url} at {time.ctime()}')
                    for success in self.valid_logins:
                        log.success(success)
        finally:
            self.stop()


    def spray(self, enumerate_users=False):

        if enumerate_users:
            sprayer = self.user_enumerator
        else:
            sprayer = self.sprayer

        ready = False
        try:
            ready = sprayer.initialize()
        except Exception as e:
            log.error(f'Unhandled error in {sprayer.__class__.__name__}.initialize(): {e}')
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())

        if not ready:
            log.error(f'Failed to initialize {sprayer.__class__.__name__}')
            return

        for password in ([None] if enumerate_users else self.options.passwords):
            for user in self.options.users:
                accepted = False
                while not accepted and not self._stop:
                    for proxy in self.proxies:
                        accepted = proxy.submit(user, password, enumerate_users)
                        if accepted:
                            break
                    if not accepted:
                        time.sleep(.1)

        # wait until finished
        while not all([not proxy.running for proxy in self.proxies]):
            log.verbose('Waiting for proxy threads to finish')
            time.sleep(2)


    def start(self):

        for proxy in self.proxies:
            if proxy is not None:
                proxy.start()

    def stop(self):

        log.debug('Stopping sprayer')
        self._stop = True
        for proxy in self.proxies:
            if proxy is not None:
                proxy.stop()
        with suppress(Exception):
            self.subnet_proxy.stop()
        # write valid users
        util.update_file(self.existent_users_file, self.existent_users)
        log.info(f'{len(self.existent_users):,} valid users written to {self.existent_users_file}')
        # write attempted logins
        util.update_file(self.tried_logins_file, self.tried_logins)
        # write valid logins
        util.update_file(self.valid_logins_file, self.valid_logins)
        log.info(f'{len(self.valid_logins):,} valid user/pass combos written to {self.valid_logins_file}')
