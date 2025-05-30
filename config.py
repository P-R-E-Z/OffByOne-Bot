# Loads env variables from .env file
from dotenv import load_dotenv
import os

from bot import DEV_GUILD_ID

load_dotenv()

# Discord bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file.")

DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")

ENV = os.getenv("ENV", "dev")

# SQLite DB path
DB_PATH = os.getenv("DB_PATH", "data/bot.db")
if not DB_PATH:
    raise ValueError("DB_PATH not found in .env file.")

# GitHub API token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in .env file.")
