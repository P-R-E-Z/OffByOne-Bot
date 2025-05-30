# Main entry point for the bot
import discord
from discord.ext import commands
from config import BOT_TOKEN
from loguru import logger
import asyncio
import os

# Guild sync for slash commands
DEV_GUILD_ID = int(os.getenv("DEV_GUILD_ID"))
ENV = os.getenv("ENV", "dev")  # default global

# from database import init_db

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Core command modules
CORE_COGS = ["moderation", "roles", "toggles", "applications"]

# Feature command modules
FEATURE_COGS = ["hooks", "updater", "memes", "coding_help", "crossposter"]

TASK_COGS = ["tasks.poll_repos", "tasks.poll_channels", "tasks.notify_pending_apps"]

ALL_COGS = CORE_COGS + FEATURE_COGS + TASK_COGS


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    try:
        if ENV == "prod":
            synced = await bot.tree.sync()
            logger.success(f"Synced {len(synced)} slash commands globally")
        else:
            synced = await bot.tree.sync(guild=discord.Object(id=DEV_GUILD_ID))
            logger.success(
                f"Synced {len(synced)} slash commands to guild {DEV_GUILD_ID}"
            )
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")


async def load_cogs():
    for cog in ALL_COGS:
        try:
            module = cog if cog.startswith("tasks.") else f"cogs.{cog}"
            await bot.load_extension(module)
            logger.success(f"Loaded cog: {cog}")
        except Exception as e:
            logger.error(f"Failed to load cog: {cog}: {e}")


async def main():
    #   await init_db()
    await load_cogs()
    await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
