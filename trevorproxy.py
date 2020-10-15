#!/usr/bin/env python3

# by TheTechromancer

import sys
import time
import logging
import argparse
from lib import util
from lib import logger
from time import sleep
from lib.proxy import *
from lib.errors import *
from shutil import which
from getpass import getpass


log = logging.getLogger('trevorspray.trevorproxy')


def main(options):

    load_balancer = SSHLoadBalancer(
        hosts=options.ssh_hosts,
        key=options.key,
        key_pass=options.key_pass,
        base_port=options.base_port,
        socks_server=True
    )

    try:

        load_balancer.start()
        log.critical(f'Listening on socks4://{options.listen_address}:{options.port}')

        # serve forever
        while 1:
            # rebuild proxy if it goes down
            for proxy in load_balancer.proxies.values():
                if not proxy.is_connected():
                    log.debug(f'SSH Proxy {proxy} went down, attempting to rebuild')
                    proxy.start()
            time.sleep(1)

    finally:
        load_balancer.stop()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Spawns a SOCKS server which round-robins requests through the specified SSH hosts')

    parser.add_argument('ssh_hosts', nargs='+', help='Round-robin load-balance through these SSH hosts (user@host)')
    parser.add_argument('-p', '--port', type=int, default=1080, help='Port for SOCKS server to listen on (default: 1080)')
    parser.add_argument('-l', '--listen-address', default='127.0.0.1', help='Listen address for SOCKS server (default: 127.0.0.1)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print extra debugging info')
    parser.add_argument('-k', '--key', help='Use this SSH key when connecting to proxy hosts')
    parser.add_argument('-kp', '--key-pass', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--base-port', default=32482, type=int, help='Base listening port to use for SOCKS proxies')

    try:

        options = parser.parse_args()

        # make sure executables exist
        for binary in SSHLoadBalancer.dependencies:
            if not which(binary):
                log.error(f'Please install {binary}')
                sys.exit(1)

        if util.ssh_key_encrypted(options.key):
            options.key_pass = getpass('SSH key password (press enter if none): ')

        main(options)


    except argparse.ArgumentError as e:
        log.error(e)
        log.error('Check your syntax')
        sys.exit(2)

    except TREVORSprayError as e:
        if options.verbose:
            import traceback
            log.error(traceback.format_exc())
        else:
            log.error(f'Encountered error (-v to debug): {e}')

    except KeyboardInterrupt:
        log.error('Interrupted')
        sys.exit(1)