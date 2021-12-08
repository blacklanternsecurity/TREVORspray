#!/usr/bin/env python3

# by TheTechromancer

import os
import sys
import logging
import argparse
import requests
from shutil import which
from pathlib import Path
from getpass import getpass

from urllib3.exceptions import InsecureRequestWarning

# Suppress only the single warning from urllib3 needed.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

package_path = Path(__file__).resolve().parent
sys.path.append(str(package_path))

from lib import logger
import lib.util as util
from lib.sprayer import TrevorSpray
from lib.errors import TREVORSprayError

log = logging.getLogger('trevorspray.cli')


def main():

    module_dir = Path(__file__).parent / 'lib/sprayers'
    module_files = list(os.listdir(module_dir))
    module_choices = []
    for file in module_files:
        file = module_dir / file
        if file.is_file() and file.suffix.lower() == '.py' and not file.stem == 'base':
            module_choices.append(file.stem)

    parser = argparse.ArgumentParser(description='Execute password sprays against O365, optionally proxying the traffic through SSH hosts')

    parser.add_argument('-u', '--users', nargs='+', help='Usernames(s) and/or file(s) containing usernames')
    parser.add_argument('-p', '--passwords', nargs='+', help='Password(s) that will be used to perform the password spray')
    parser.add_argument('-r', '--recon', metavar='DOMAIN', nargs='+', help='Retrieves MX records and info related to authentication, email, Azure, Microsoft 365, etc.')
    parser.add_argument('-f', '--force', action='store_true', help='Forces the spray to continue and not stop when multiple account lockouts are detected')
    parser.add_argument('-d', '--delay', type=float, default=0, help='Sleep for this many seconds between requests')
    parser.add_argument('-ld', '--lockout-delay', type=float, default=0, help='Sleep for this many additional seconds when a lockout is encountered')
    parser.add_argument('-j', '--jitter', type=float, default=0, help='Add a random delay of up to this many seconds between requests')
    parser.add_argument('--url', help='The URL to spray against')
    parser.add_argument('-v', '--verbose', '--debug', action='store_true', help='Show which proxy is being used for each request')
    parser.add_argument('-s', '--ssh', default=[], metavar='USER@SERVER', nargs='+', help='Round-robin load-balance through these SSH hosts (user@host) NOTE: Current IP address is also used once per round')
    parser.add_argument('-i', '-k', '--key', help='Use this SSH key when connecting to proxy hosts')
    parser.add_argument('-kp', '--key-pass', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-b', '--base-port', default=33482, type=int, help='Base listening port to use for SOCKS proxies')
    parser.add_argument('-n', '--no-current-ip', action='store_true', help='Don\'t spray from the current IP, only use SSH proxies')
    parser.add_argument('-nl', '--no-loot', action='store_true', help='Don\'t execute loot activites for valid accounts')
    parser.add_argument('-t', '--timeout', type=float, default=10, help='Connection timeout in seconds (default: 10)')
    parser.add_argument('-m', '--module', choices=module_choices, default='msol', help='Spray module to use (default: msol)')

    try:

        options = parser.parse_args()

        if options.verbose:
            logging.getLogger('trevorspray').setLevel(logging.DEBUG)
            logging.getLogger('trevorproxy').setLevel(logging.DEBUG)

        if not (options.users and options.passwords):
            if not options.recon:
                log.error('Please specify --users and --passwords, or --recon')
                sys.exit(2)
        else:
            options.users = util.files_to_list(options.users)

        if options.no_current_ip and not options.ssh:
            log.error('Cannot specify --no-current-ip without giving --ssh hosts')
            sys.exit(1)

        if options.ssh and util.ssh_key_encrypted(options.key):
            options.key_pass = getpass('SSH key password (press enter if none): ')

        log.info(f'Command: {" ".join(sys.argv)}')
        sprayer = TrevorSpray(options)
        sprayer.go()

    except argparse.ArgumentError as e:
        log.error(e)
        log.error('Check your syntax')
        sys.exit(2)

    except TREVORSprayError as e:
        log.error(str(e))

    except Exception as e:
        if options.verbose:
            import traceback
            log.error(traceback.format_exc())
        else:
            log.error(f'Encountered error (-v to debug): {e}')

    except KeyboardInterrupt:
        log.error('Interrupted')
        sys.exit(1)

if __name__ == '__main__':
    main()