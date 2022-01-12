import json
import logging
import requests
import tldextract
import subprocess as sp
from pathlib import Path
import lxml.etree as etree
from pygments import highlight
from contextlib import suppress
from urllib.parse import urlparse
from pygments.lexers.html import XmlLexer
from pygments.lexers.data import JsonLexer
from pygments.formatters import TerminalFormatter

log = logging.getLogger('trevorspray.util')


windows_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36 Edg/96.0.1054.43'


def highlight_json(j):

    if type(j) in [dict, list, set, tuple]:
        j = json.dumps(j, indent=4)

    return highlight(j, JsonLexer(), TerminalFormatter())


def highlight_xml(x):

    if type(x) == str:
        x = str.encode()

    with suppress(Exception):
        x = etree.tostring(etree.fromstring(x), pretty_print=True)

    return highlight(x, XmlLexer(), TerminalFormatter())


def files_to_list(l):

    new_list = dict()
    for entry in l:
        entry = str(entry)
        try:
            with open(entry) as f:
                for line in f.readlines():
                    entry = line.strip('\r\n').lower()
                    new_list[entry] = True
        except OSError:
            if entry and entry not in new_list:
                new_list[entry] = True

    return new_list


def update_file(filename, l):
    '''
    Update file "filename" with entries from list "l"
    Only unique entries are added
    '''

    final_list = dict()
    try:
        with open(str(filename)) as f:
            for line in f:
                final_list[line.strip()] = True
    except OSError as e:
        log.debug(f'Could not read file {filename}: {e}')
    for entry in l:
        final_list[entry] = True
    with open(filename, 'w') as f:
        f.writelines([f'{e}\n' for e in final_list])


def read_file(filename, key=lambda x: True):

    final_list = dict()
    try:
        with open(str(filename)) as f:
            for line in f.readlines():
                entry = line.strip()
                if key(entry):
                    final_list[entry] = True
    except OSError as e:
        log.debug(f'Could not read file {filename}: {e}')

    return final_list


def ssh_key_encrypted(f=None):

    if f is None:
        f = Path.home() / '.ssh/id_rsa'

    try:
        p = sp.run(['ssh-keygen', '-y', '-P', '', '-f', str(f)], stdout=sp.DEVNULL, stderr=sp.PIPE)
        if not 'incorrect' in p.stderr.decode():
            return False
    except:
        pass
    return True


def is_domain(d):

    extracted = tldextract.extract(d)
    if extracted.domain and not extracted.subdomain:
        return True
    return False


def is_subdomain(d):

    extracted = tldextract.extract(d)
    if extracted.domain and extracted.subdomain:
        return True
    return False


def is_url(d):

    parsed = urlparse(d)
    if parsed.scheme or '/' in parsed.path or parsed.query:
        return True
    return False


def download_file(url, filename, **kwargs):

    with requests.get(url, stream=True, **kwargs) as response:
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):  
                f.write(chunk)