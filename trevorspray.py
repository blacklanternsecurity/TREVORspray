#!/usr/bin/env python3

# by TheTechromancer

import sys
import logging
import argparse
from lib import logger
import lib.util as util
from shutil import which
from getpass import getpass
from lib.sprayer import TrevorSpray
from lib.proxy import SSHLoadBalancer
from lib.errors import TREVORSprayError


log = logging.getLogger('trevorspray.cli')


def main(options):

    log.info(f'Command: {" ".join(sys.argv)}')
    sprayer = TrevorSpray(options)
    sprayer.go()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Execute password sprays against O365, optionally proxying the traffic through SSH hosts')

    parser.add_argument('-e', '--emails', nargs='+', help='Emails(s) and/or file(s) filled with emails')
    parser.add_argument('-p', '--passwords', nargs='+', help='Password(s) that will be used to perform the password spray')
    parser.add_argument('-r', '--recon', metavar='DOMAIN', nargs='+', help='Retrieves info related to authentication, email, Azure, Microsoft 365, etc.')
    parser.add_argument('-f', '--force', action='store_true', help='Forces the spray to continue and not stop when multiple account lockouts are detected')
    parser.add_argument('-d', '--delay', type=float, default=0, help='Sleep for this many seconds between requests')
    parser.add_argument('-j', '--jitter', type=float, default=0, help='Add a random delay of up to this many seconds between requests')
    parser.add_argument('-u', '--url', default='https://login.microsoft.com/common/oauth2/token', help='The URL to spray against (default is https://login.microsoft.com)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show which proxy is being used for each request')
    parser.add_argument('-s', '--ssh', default=[], metavar='USER@SERVER', nargs='+', help='Round-robin load-balance through these SSH hosts (user@host) NOTE: Current IP address is also used once per round')
    parser.add_argument('-i', '-k', '--key', help='Use this SSH key when connecting to proxy hosts')
    parser.add_argument('-kp', '--key-pass', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-b', '--base-port', default=33482, type=int, help='Base listening port to use for SOCKS proxies')
    parser.add_argument('-n', '--no-current-ip', action='store_true', help='Don\'t spray from the current IP, only use SSH proxies')

    try:

        options = parser.parse_args()

        if not (options.emails and options.passwords):
            if not options.recon:
                log.error('Please specify --emails and --passwords')
        else:
            options.emails = util.files_to_list(options.emails)


        if options.no_current_ip and not options.ssh:
            log.error('Cannot specify --no-current-ip without giving --ssh hosts')
            sys.exit(1)

        # make sure executables exist
        for binary in SSHLoadBalancer.dependencies:
            if not which(binary):
                log.error(f'Please install {binary}')
                sys.exit(1)

        if options.ssh and util.ssh_key_encrypted(options.key):
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