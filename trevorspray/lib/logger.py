### LOGGING ###

import sys
import logging
from copy import copy
from pathlib import Path

### PRETTY COLORS ###


class ColoredFormatter(logging.Formatter):
    color_mapping = {
        "DEBUG": 242,  # grey
        "VERBOSE": 242,  # grey
        "INFO": 69,  # blue
        "SUCCESS": 118,  # green
        "WARNING": 208,  # orange
        "ERROR": 196,  # red
        "CRITICAL": 196,  # red
    }

    char_mapping = {
        "DEBUG": "DBUG",
        "VERBOSE": "VERB",
        "INFO": "INFO",
        "SUCCESS": "SUCC",
        "WARNING": "WARN",
        "ERROR": "ERRR",
        "CRITICAL": "CRIT",
    }

    prefix = "\033[1;38;5;"
    suffix = "\033[0m"

    def __init__(self, pattern):
        super().__init__(pattern)

    def format(self, record):
        colored_record = copy(record)
        levelname = colored_record.levelname
        levelchar = self.char_mapping.get(levelname, "INFO")
        seq = self.color_mapping.get(levelname, 15)  # default white
        colored_levelname = f"{self.prefix}{seq}m[{levelchar}]{self.suffix}"
        if levelname == "CRITICAL":
            colored_record.msg = f"{self.prefix}{seq}m{colored_record.msg}{self.suffix}"
        colored_record.levelname = colored_levelname

        return logging.Formatter.format(self, colored_record)


def addLoggingLevel(levelName, levelNum, methodName=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        raise AttributeError("{} already defined in logging module".format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError("{} already defined in logging module".format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError("{} already defined in logger class".format(methodName))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


# custom logging levels
addLoggingLevel("SUCCESS", 25)
addLoggingLevel("VERBOSE", 15)


### LOG TO STDOUT AND FILE ###

log_dir = Path.home() / ".trevorspray"
log_file = log_dir / "trevorspray.log"
log_dir.mkdir(exist_ok=True)

console_handler = logging.StreamHandler(sys.stdout)
if any([x.lower() in ["--debug", "--verbose", "-v"] for x in sys.argv]):
    console_handler.addFilter(lambda x: x.levelno >= logging.DEBUG)
else:
    console_handler.addFilter(lambda x: x.levelno >= logging.VERBOSE)
console_handler.setFormatter(ColoredFormatter("%(levelname)s %(message)s"))
file_handler = logging.FileHandler(str(log_file))
file_handler.addFilter(lambda x: x.levelno >= logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

root_logger = logging.getLogger("trevorspray")
root_logger.handlers = [console_handler, file_handler]
root_logger.setLevel(logging.DEBUG)

proxy_logger = logging.getLogger("trevorproxy")
proxy_logger.handlers = [console_handler, file_handler]
proxy_logger.setLevel(logging.DEBUG)
