import logging
import time
from logging.handlers import RotatingFileHandler

import os
import sys
from pathlib import Path

from .commands_handler import *
from .messages_handler import *

Path('logs/').mkdir(exist_ok=True)

file_name = os.path.join('logs', time.strftime("%Y-%m-%d-%H-%M-%S") + '.log')
file_handler = RotatingFileHandler(file_name, maxBytes=1024 * 1024 * 1, backupCount=5)

stream_handler = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, handlers=[stream_handler, file_handler])
