import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.settings import BotSettings

settings = BotSettings()

Path('logs/').mkdir(exist_ok=True)

file_name = os.path.join('logs', time.strftime("%Y-%m-%d-%H-%M-%S") + '.log')
file_handler = RotatingFileHandler(file_name, maxBytes=1024 * 1024 * 1, backupCount=5)

stream_handler = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, handlers=[stream_handler, file_handler])  # change level to DEBUG if needed

import app.database
import app.handlers
