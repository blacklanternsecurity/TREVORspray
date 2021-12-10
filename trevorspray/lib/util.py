import logging
import tldextract
import subprocess as sp
from pathlib import Path
from pygments import highlight
from urllib.parse import urlparse
from pygments.lexers.data import JsonLexer
from pygments.formatters import TerminalFormatter

log = logging.getLogger('trevorspray.util')

def highlight_json(j):

    return highlight(j, JsonLexer(), TerminalFormatter())


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
        log.verbose(f'Could not read file {filename}: {e}')
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
        log.verbose(f'Could not read file {filename}: {e}')

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