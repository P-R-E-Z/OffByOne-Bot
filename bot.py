# Main entry point for the bot
import botocore.eventstream
import discord
from discord.ext import commands
from discord.ext.commands import bot

from config import BOT_TOKEN
from loguru import logger
import asyncio

from database import init_db

intents = discord.Intents.all()
boto3 = commands.Bot(command_prefix="!", intents=intents)

# Core command modules
CORE_COGS = [
    "moderation",
    "roles",
    "toggles",
    "applications"
]

# Feature command modules
FEATURE_COGS = [
    "hooks",
    "updater",
    "memes",
    "coding_help",
    "crossposter"
]

ALL_COGS = CORE_COGS + FEATURE_COGS + TASK_COGS

@bot.event 
async def on_ready():
    logger.info(f"Logged in as {bot.user.name}")

async def load_cogs():
    for cog in ALL_COGS:
        try:
            modul = cog if cog.startswith("tasks.") else f"cogs.{cog}"
            await bot.load_extension(module)
            logger.success(f"Loaded cog: {cog}")
        except Exception as e:
            logger.error(f"Failed to load cog: {cog}: {e}")
            
async def main():
    await init_db()
    await load_cogs()
    await bot.start(BOT_TOKEN)
    
if __name__ == "__main__":
    asyncio.run(main())