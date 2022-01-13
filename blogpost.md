### Password spraying is one of the great joys of pentesting. Or at least, it used to be.

Classically password spraying has been the single lowest-effort and highest-yield technique for gaining an initial foothold in an organization. This made it pretty fun. You start by gathering up a big list of emails, then you kick off a spray with a stupid password like "Spring2022!", and spend the next hour getting disproportionately large and debatably undeserved hits of dopamine as you slowly discover just how many employees are using that stupid password.

But alas, with increasing Multi-Factor coverage and defensive countermeasures like smart lockout, password spraying becoming more and more of a pain.

![slow-password-sprays](https://user-images.githubusercontent.com/20261699/149404528-8c89f989-299a-4bd0-831c-c16c908a9f86.png)

As pentesters we've been forced to dial back the intensity of our password sprays so that they take hours or days to finish. And even when we find a valid credential, it sometimes doesn't lead anywhere thanks to security policies like MFA. Overall, it's a similar upward trend to what's happening in the phishing space, which is a whole different blog post. But I digress.

I suppose that since we work in cybersecurity we should be happy about these changes since it means better security for organizations. Afterall the goal of our industry is to make hackers' jobs harder. But since we're hackers and it's our job to hack stuff, it's hard to sit idly by and let our favorite passtime of password spraying go the way of the dodo.

What I'm trying to say is that we're frustrated. And when hackers are frustrated they write code. So it is with great delight that we are open-sourcing some new tools which are the product of our frustration and will hopefully help to make password spraying fun again.

# Introducing TREVORproxy and TREVORspray 2.0

When I set out to write these tools, there were a lot of problems I wanted to solve. But the biggest one was **Smart Lockout**.

**Smart Lockout** tries to lock out attackers without locking out legitimate users. So basically it's a fancy word for a lockout mechanism that considers the source IP address when locking an account. There are nuances -- like how smart lockout is often powered by machine learning, which makes it inconsistent and unpredictable -- but this is the gist of it.

![smart-lockout-at-work](https://user-images.githubusercontent.com/20261699/149381950-add2eceb-e467-4259-a24b-dfacfdef4b2c.gif)

## TREVORproxy

[**TREVORproxy**](https://github.com/blacklanternsecurity/TREVORproxy) is a simple SOCKS proxy that helps avoid Smart Lockout by load-balancing your requests between multiple IPs. It accomplishes this with built-in Linux features -- no complex OpenVPN setups or strange firewall configurations. You can use this proxy with BurpSuite, your spraying tool of choice, or even your web browser.

There are two techniques that TREVORproxy uses to spread your requests across multiple IPs: an **SSH Proxy** and a **Subnet Proxy**.

### SSH Proxy
The SSH Proxy is pretty straightforward. You give TREVORproxy some hosts that support SSH, and it sends your traffic through them, making sure to balance equally between all the hosts.
~~~bash
trevorproxy ssh root@1.2.3.4 root@4.3.2.1
~~~
![ssh-proxy](https://user-images.githubusercontent.com/20261699/149403633-3b6259c4-6c13-4ae5-abe6-498024a155f5.gif)

### Subnet Proxy
The subnet proxy can be a lot of fun. If you have access to a `/64` IPv6 subnet ([Linode](https://www.linode.com/) is perfect for this), TREVORproxy will load-balance your requests across **eighteen quintillion** (18,446,744,073,709,551,616) unique source addresses.

Note that if you're using the subnet proxy in IPv6 mode, your target must also support IPv6.

~~~bash
sudo trevorproxy subnet -s dead:beef::0/64 -i eth0
~~~
![subnet-proxy](https://user-images.githubusercontent.com/20261699/142468206-4e9a46db-b18b-4969-8934-19d1f3837300.gif)

## TREVORspray

[**TREVORspray**](https://github.com/blacklanternsecurity/TREVORspray) is a modular password sprayer with built-in TREVORproxy support. It has the following features:
  - Threads, lots of threads
  - Multiple modules
      - `msol` (Office 365)
      - `adfs` (Active Directory Federation Services)
      - `okta` (Okta SSO)
      - `anyconnect` (Cisco VPN)
      - custom modules (easy to make!)
  - Tells you the status of each account: if it exists, is locked, has MFA enabled, etc. (when supported)
  - Automatic cancel/resume (remembers already-tried user/pass combos in `~/.trevorspray/tried_logins.txt`)
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

### TREVORspray example
Note the automatic MFA bypass checks in the demo below!
~~~bash
trevorspray -u emails.txt -p 'Spring2022!' --ssh root@1.2.3.4 root@4.3.2.1
~~~

![trevorspray-demo](https://user-images.githubusercontent.com/20261699/149219712-8549e15c-2eee-4d7a-a615-e8882b693c3f.gif)


## Conclusion

By combining the IP-shuffling capability of TREVORproxy and TREVORspray's customizable `--delay`, `--jitter`, and `--lockout-delay` options, you can confuse Smart Lockout and boost the speed and effectiveness of your password sprays. For more examples and in-depth explanations of these concepts, please see the projects' READMEs.

- https://github.com/blacklanternsecurity/TREVORproxy
- https://github.com/blacklanternsecurity/TREVORspray

Happy spraying!

-[TheTechromancer](https://twitter.com/thetechr0mancer)