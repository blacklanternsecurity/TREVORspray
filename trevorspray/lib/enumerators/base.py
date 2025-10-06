import logging
from ..sprayers.base import BaseSprayModule

log = logging.getLogger("trevorspray.enumerators.base")

class Enumerator(BaseSprayModule):
    """
    Base class for all enumerator modules
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retries = 0  # Don't retry enumeration attempts

    def enumerate(self, username):
        """
        Enumerate a user's existence
        Returns: (valid, exists, locked, msg)
        """
        raise NotImplementedError("Enumerator modules must implement enumerate()")

    def check_response(self, response):
        """
        Check the response from an enumeration attempt
        Returns: (valid, exists, locked, msg)
        """
        raise NotImplementedError("Enumerator modules must implement check_response()") 