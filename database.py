# Database connection
import os
import aiosqlite
from loguru import logger
from schemas import models

DB_PATH = "data/bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(models.CREATE_USERS_TABLE)
        await db.execute(models.CREATE_APPLICATIONS_TABLE)
        await db.execute(models.CREATE_APPROVED_ROLES_TABLE)
        await db.execute(models.CREATE_PENDING_APPS_TABLE)
        await db.execute(models.CREATE_ROLES_TABLE)
