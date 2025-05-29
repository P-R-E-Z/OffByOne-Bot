# Configures loguru logging for console and rotating file output
import os
import sys
from loguru import logger

LOG_DIR = os.path.join(os.path.abspath(__file__ + "/../../"), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{message}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>",
)
logger.add(
    os.path.join(LOG_DIR, "bot.log"),
    rotation="1 week",
    retention="1 month",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
)
logger.info("Loguru logger initialized.")
