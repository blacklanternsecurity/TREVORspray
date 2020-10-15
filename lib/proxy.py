import os
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



class IPTables:

    def __init__(self, proxies, address=None, port=None):

        if address is None:
            self.address = '127.0.0.1'
        else:
            self.address = str(address)
        if port is None:
            self.port = 1080
        else:
            self.port = int(port)

        self.proxies = [p for p in proxies if p is not None]
        self.args_pre = []
        if os.geteuid() != 0:
            self.args_pre = ['sudo']

        self.iptables_rules = []


    def start(self):

        log.debug('Creating iptables rules')

        current_ip = False
        for i,proxy in enumerate(self.proxies):
            if proxy is not None:
                iptables_add = ['iptables', '-A']
                iptables_main = ['OUTPUT', '-t', 'nat', '-d', f'{self.address}', '-o', 'lo', '-p', \
                    'tcp', '--dport', f'{self.port}', '-j', 'DNAT', '--to-destination', f'127.0.0.1:{proxy.port}']

                # if this isn't the last proxy
                if not i == len(self.proxies)-1:
                    iptables_main += ['-m', 'statistic', '--mode', 'nth', '--every', f'{len(self.proxies)-i}', '--packet', '0']

                self.iptables_rules.append(iptables_main)

                cmd = self.args_pre + iptables_add + iptables_main
                log.debug('Command: ' + ' '.join(cmd))
                sp.run(cmd)


    def stop(self):

        log.debug('Cleaning up iptables rules')

        for rule in self.iptables_rules:
            iptables_del = ['iptables', '-D']
            cmd = self.args_pre + iptables_del + rule
            log.debug('Command: ' + ' '.join(cmd))
            sp.run(cmd)



class SSHLoadBalancer:

    dependencies = ['ssh', 'ss', 'iptables', 'sudo']

    def __init__(self, hosts, key=None, key_pass=None, base_port=33482, current_ip=False, socks_server=False):

        self.args = dict()
        self.hosts = hosts
        self.key = key
        self.key_pass = key_pass
        self.base_port = base_port
        self.current_ip = current_ip
        self.proxies = dict()
        self.socks_server = socks_server

        if self.key is not None:
            self.args['i'] = str(Path(key).absolute())

        for i,host in enumerate(hosts):
            port = self.base_port + i
            proxy = SSHProxy(host, port, key, key_pass, ssh_args=self.args)
            self.proxies[str(proxy)] = proxy

        if current_ip:
            self.proxies['None'] = None

        self.proxy_round_robin = list(self.proxies.values())
        self.round_robin_counter = 0

        self.iptables = IPTables(list(self.proxies.values()))


    def start(self, timeout=30):

        [p.start(wait=False) for p in self.proxies.values() if p is not None]            

        # wait for them all to start
        left = int(timeout)
        while not all([p.is_connected() for p in self.proxies.values() if p is not None]):
            left -= 1
            for p in self.proxies.values():
                if p is not None and (not p.sh.is_alive() or left <= 0):
                    raise SSHProxyError(f'Failed to start SSH proxy {p}: {p.command}')
            sleep(1)

        if self.socks_server:
            self.iptables.start()


    def stop(self):

        [proxy.stop() for proxy in self.proxies.values() if proxy is not None]
        if self.socks_server:
            self.iptables.stop()


    def __next__(self):
        '''
        Yields proxies in round-robin fashion forever
        Note that a proxy can be "None" if current_ip is specified
        '''

        proxy_num = self.round_robin_counter % len(self.proxies)
        proxy = self.proxy_round_robin[proxy_num]
        self.round_robin_counter += 1
        return proxy


    def __enter__(self):

        return self


    def __exit__(self, exc_type, exc_value, exc_traceback):

        debug.info('Shutting down proxies')
        self.stop()