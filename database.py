# Inits SQLite database using aiosqlite & schema constants
import aiosqlite
from loguru import logger
from config import DB_PATH
from schemas import models


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(models.CREATE_APPLICATIONS_TABLE)
        await db.execute(models.CREATE_APPROVED_ROLES_TABLE)
        await db.execute(models.CREATE_REPO_HOOKS_TABLE)
        await db.execute(models.CREATE_CHANNEL_HOOKS_TABLE)
        await db.execute(models.CREATE_TOGGLES_TABLE)
        await db.execute(models.CREATE_SERVER_CONFIGS_TABLE)
        await db.execute(models.CREATE_APPLICATION_CHANNELS_TABLE)
        await db.execute(models.CREATE_ROLE_MAPPINGS_TABLE)
        await db.commit()
        logger.info("Database initialized.")
