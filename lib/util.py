import subprocess as sp
from pathlib import Path
from pygments import highlight
from pygments.lexers.data import JsonLexer
from pygments.formatters import TerminalFormatter


def highlight_json(j):

    return highlight(j, JsonLexer(), TerminalFormatter())


def files_to_list(l):

    new_list = []
    for entry in l:
        entry = str(entry)
        try:
            with open(entry) as f:
                for e in f.readlines():
                    e = e.strip('\r\n').lower()
                    if e and e not in new_list:
                        new_list.append(e)
        except OSError:
            if entry and entry not in new_list:
                new_list.append(entry)

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
    except OSError:
        pass
    for entry in l:
        final_list[entry] = True
    with open(filename, 'w') as f:
        f.writelines([f'{e}\n' for e in final_list])


def read_file(filename, key=lambda x: x):

    final_list = set()
    try:
        with open(str(filename)) as f:
            for e in f.readlines():
                e = e.strip()
                if key(e):
                    final_list.add(e)
    except OSError:
        pass

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