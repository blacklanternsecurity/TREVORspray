### LOGGING ###

import sys
import logging
from copy import copy
from pathlib import Path

### PRETTY COLORS ###


class ColoredFormatter(logging.Formatter):

    color_mapping = {
        'DEBUG':    242, # grey
        'INFO':     69,  # blue
        'WARNING':  208, # orange
        'ERROR':    196, # red
        'CRITICAL': 118, # green
    }

    char_mapping = {
        'DEBUG':    'DBUG',
        'INFO':     'INFO',
        'WARNING':  'WARN',
        'ERROR':    'WARN',
        'CRITICAL': 'SUCC',
    }

    prefix = '\033[1;38;5;'
    suffix = '\033[0m'

    def __init__(self, pattern):

        super().__init__(pattern)


    def format(self, record):

        colored_record = copy(record)
        levelname = colored_record.levelname
        levelchar = self.char_mapping.get(levelname, 'INFO')
        seq = self.color_mapping.get(levelname, 15) # default white
        colored_levelname = f'{self.prefix}{seq}m[{levelchar}]{self.suffix}'
        if levelname == 'CRITICAL':
            colored_record.msg = f'{self.prefix}{seq}m{colored_record.msg}{self.suffix}'
        colored_record.levelname = colored_levelname

        return logging.Formatter.format(self, colored_record)


### LOG TO STDOUT AND FILE ###

log_dir = Path.home() / '.trevorspray'
log_file = log_dir / 'trevorspray.log'
log_dir.mkdir(exist_ok=True)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter('%(levelname)s %(message)s'))
file_handler = logging.FileHandler(str(log_file))
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

root_logger = logging.getLogger('trevorspray')
root_logger.handlers = [console_handler, file_handler]
root_logger.setLevel(logging.DEBUG)
