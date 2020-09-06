import sys
import logging
from sh import ssh
from . import logger
from time import sleep
import subprocess as sp
from pathlib import Path
from .errors import TREVORSprayError

log = logging.getLogger('trevorspray.proxy')



class SSHProxyError(TREVORSprayError):
    pass



class SSHProxy:

    def __init__(self, host, port, key=None, key_pass='', ssh_args={}):

        self.host = host
        self.port = port
        self.key = key
        self.key_pass = key_pass
        self.ssh_args = dict(ssh_args)
        self.ssh_args['D'] = str(port)
        self.sh = None
        self.command = ''
        self._ssh_stdout = ''
        self.running = False


    def start(self, wait=True, timeout=30):

        self.stop()
        log.debug(f'Opening SSH connection to {self.host}')

        self._ssh_stdout = ''
        self._password_entered = False
        self.sh = ssh(
            self.host,
            _out=self._enter_password,
            _out_bufsize=0,
            _tty_in=True,
            _unify_ttys=True,
            _long_sep=' ',
            _bg=True,
            **self.ssh_args
        )
        self.command = b' '.join(self.sh.cmd).decode()
        log.debug(self.command)

        left = int(timeout)
        if wait:
            while not self.is_connected():
                left -= 1
                if left <= 0 or not self.sh.is_alive():
                    raise SSHProxy(f'Failed to start SSHProxy {self}')
                else:
                    sleep(1)


    def stop(self):

        try:
            self.sh.process.terminate()
        except:
            try:
                self.sh.process.kill()
            except:
                pass


    def _enter_password(self, char, stdin):

        if self._password_entered or not char:
            # save on CPU
            sleep(.01)
        else:
            self._ssh_stdout += char
            if 'pass' in self._ssh_stdout and self._ssh_stdout.endswith(': '):
                stdin.put(f'{self.key_pass}\n')


    def is_connected(self):

        if self.sh is None:
            return False

        netstat = sp.run(['ss', '-ntlp'], stderr=sp.DEVNULL, stdout=sp.PIPE)
        if not f' 127.0.0.1:{self.port} ' in netstat.stdout.decode():
            log.debug(f'Waiting for {" ".join([x.decode() for x in self.sh.cmd])}')
            self.running = False
        else:
            self.running = True
            self._password_entered = True

        return self.running


    def __hash__(self):

        return hash(str(self))


    def __str__(self):

        return f'socks4://127.0.0.1:{self.port}'


    def __repr__(self):

        return str(self)



class SSHLoadBalancer:

    def __init__(self, hosts, key=None, key_pass=None, base_port=33482, current_ip=True):

        self.args = dict()
        self.hosts = hosts
        self.key = key
        self.key_pass = key_pass
        self.base_port = base_port
        self.current_ip = current_ip
        self.proxies = dict()

        if self.key is not None:
            self.args['i'] = str(Path(key).absolute())

        for i,host in enumerate(hosts):
            port = self.base_port + i
            proxy = SSHProxy(host, port, key, key_pass, ssh_args=self.args)
            self.proxies[str(proxy)] = proxy

        self.proxy_round_robin = list(self.proxies.values())
        self.round_robin_counter = 0


    def start(self, timeout=30):

        for p in self.proxies.values():
            p.start(wait=False)

        # wait for them all to start
        left = int(timeout)
        while not all([p.is_connected() for p in self.proxies.values()]):
            left -= 1
            for p in self.proxies.values():
                if not p.sh.is_alive() or left <= 0:
                    raise SSHProxyError(f'Failed to start SSH proxy {p}: {p.command}')
            sleep(1)


    def stop(self):

        [proxy.stop() for proxy in self.proxies.values()]


    def __next__(self):

        proxy_num = self.round_robin_counter % (len(self.proxies) + (1 if self.current_ip else 0))
        try:
            proxy = self.proxy_round_robin[proxy_num]
        except IndexError:
            proxy = None
        self.round_robin_counter += 1
        return proxy


    def __enter__(self):

        return self


    def __exit__(self, exc_type, exc_value, exc_traceback):

        debug.info('Shutting down proxies')
        self.stop()