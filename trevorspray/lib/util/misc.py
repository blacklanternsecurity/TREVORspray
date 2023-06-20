import json
import logging
import requests
import tldextract
from time import sleep
import subprocess as sp
from pathlib import Path
import lxml.etree as etree
from pygments import highlight
from contextlib import suppress
from urllib.parse import urlparse
from pygments.lexers.html import XmlLexer
from pygments.lexers.data import JsonLexer
from requests.exceptions import RequestException
from pygments.formatters import TerminalFormatter

log = logging.getLogger("trevorspray.util.misc")


windows_user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1"


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
            with open(entry, errors="ignore") as f:
                for line in f.readlines():
                    entry = line.strip("\r\n").lower()
                    new_list[entry] = True
        except OSError:
            if entry and entry not in new_list:
                new_list[entry] = True

    return new_list


def update_file(filename, l):
    """
    Update file "filename" with entries from list "l"
    Only unique entries are added
    """

    final_list = dict()
    try:
        with open(str(filename)) as f:
            for line in f:
                final_list[line.strip()] = True
    except OSError as e:
        log.debug(f"Could not read file {filename}: {e}")
    for entry in l:
        final_list[entry] = True
    with open(filename, "w") as f:
        f.writelines([f"{e}\n" for e in final_list])


def read_file(filename, key=lambda x: True):
    final_list = dict()
    try:
        with open(str(filename)) as f:
            for line in f.readlines():
                entry = line.strip()
                if key(entry):
                    final_list[entry] = True
    except OSError as e:
        log.debug(f"Could not read file {filename}: {e}")

    return final_list


def ssh_key_encrypted(f=None):
    if f is None:
        f = Path.home() / ".ssh/id_rsa"

    try:
        p = sp.run(
            ["ssh-keygen", "-y", "-P", "", "-f", str(f)],
            stdout=sp.DEVNULL,
            stderr=sp.PIPE,
        )
        if not "incorrect" in p.stderr.decode():
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
    if parsed.scheme or "/" in parsed.path or parsed.query:
        return True
    return False


def download_file(url, filename, **kwargs):
    log.debug(f"Downloading file from {url} to {filename}, {kwargs}")
    with request("GET", url, stream=True, **kwargs) as response:
        text = getattr(response, "text", "")
        status_code = getattr(response, "status_code", 0)
        log.debug(f"Download result: HTTP {status_code}, Size: {len(text)}")
        if status_code != 0:
            response.raise_for_status()
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)


def request(*args, **kwargs):
    retries = kwargs.pop("retries", 3)
    session = kwargs.pop("session", None)

    prepared = False
    if len(args) > 1:
        url = args[1]
    elif len(args) == 1:
        url = args[0]
        if type(url) == requests.models.PreparedRequest:
            prepared = url
            url = str(url.url)
    else:
        url = kwargs.get("url", "")

    if not prepared and not args and "method" not in kwargs:
        kwargs["method"] = "GET"

    if not "timeout" in kwargs:
        kwargs["timeout"] = 10

    if prepared:
        headers = prepared.headers
    else:
        headers = kwargs.get("headers", {})

    if "User-Agent" not in headers:
        headers.update({"User-Agent": windows_user_agent})
    if prepared:
        prepared.headers = headers
    else:
        kwargs["headers"] = headers

    if not "verify" in kwargs:
        kwargs["verify"] = False

    while retries == "infinite" or retries >= 0:
        try:
            if prepared:
                logstr = f"Web Request: {prepared.method} {prepared.url} {prepared.headers}, {str(kwargs)}"
            else:
                logstr = f"Web request: {str(args)}, {str(kwargs)}"
            log.debug(logstr)
            if session is not None:
                if prepared:
                    response = session.send(*args, **kwargs)
                else:
                    response = session.request(*args, **kwargs)
            else:
                response = requests.request(*args, **kwargs)
            log.debug(
                f"Web response: {response} (Length: {len(response.content)}) headers: {response.headers}"
            )
            return response
        except RequestException as e:
            log.debug(f"Web error: {e}")
            if retries != "infinite":
                retries -= 1
            if retries == "infinite" or retries >= 0:
                log.warning(f'Error requesting "{url}", retrying...')
                sleep(2)
            else:
                return e
