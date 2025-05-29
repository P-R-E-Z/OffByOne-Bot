# Inits SQLite database using aiosqlite & schema constants
import aiosqlite
from loguru import logger
from weaviate.connect.executor import execute

from config import DB_PATH
from schema import models


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        awaitdb.execute(models.CREATE_APPLICATIONS_TABLE)
        awaitdb.execute(models.CREATE_APPROVED_ROLES_TABLE)
        awaitdb.execute(models.CREATE_REPO_HOOKS_TABLE)
        awaitdb.execute(models.CREATE_CHANNEL_HOOKS_TABLE)
        awaitdb.execute(models.CREATE_TOGGLES_TABLE)
        logger.info("Database initialized.")
