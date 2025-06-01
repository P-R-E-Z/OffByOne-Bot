# Main entry point for the bot
import discord
from discord.ext import commands
from config import BOT_TOKEN
from loguru import logger
import asyncio
import os
import glob
import signal
import sys
from database import init_db


def discover_cogs_from_directory(directory_path: str, module_prefix: str) -> list[str]:
    """
    Dynamically discovers Python files in a given directory that are likely cogs.
    Assumes cog files are directly in the directory_path and not in sub-subdirectories.
    """
    cog_files = glob.glob(os.path.join(directory_path, "*.py"))
    discovered_extensions = []
    for f_path in cog_files:
        file_name = os.path.basename(f_path)
        if file_name.startswith("__init__"):  # Skip __init__.py files
            continue
        module_name = os.path.splitext(file_name)[0]
        discovered_extensions.append(f"{module_prefix}.{module_name}")
    return discovered_extensions


# Guild sync for slash commands
DEV_GUILD_ID_STR = os.getenv("DEV_GUILD_ID")
DEV_GUILD_ID = (
    int(DEV_GUILD_ID_STR) if DEV_GUILD_ID_STR and DEV_GUILD_ID_STR.isdigit() else 0
)
ENV = os.getenv("ENV", "dev")  # default global

# Debug Logging
logger.info(f"Environment: {ENV}")
if DEV_GUILD_ID != 0:
    logger.info(f"Dev Guild ID: {DEV_GUILD_ID}")
else:
    logger.info(
        "Dev Guild ID not set or invalid, will use global sync fallback in 'dev' env."
    )

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Discover cogs from the 'cogs' directory (e.g., cogs.moderation)
cogs_directory = "cogs"
standard_cogs = discover_cogs_from_directory(cogs_directory, "cogs")

# Discover cogs from the 'tasks' directory (e.g., tasks.poll_repos)
tasks_directory = "tasks"
task_cogs = discover_cogs_from_directory(tasks_directory, "tasks")

ALL_COGS = standard_cogs + task_cogs
logger.info(f"Discovered extensions to load: {ALL_COGS}")
# End of dynamic cog discovery


async def load_cogs():
    """Loads cogs with detailed error reporting and recover"""
    loaded_cogs = []
    failed_cogs = []

    if not ALL_COGS:
        logger.warning("No cogs were discovered to load.")
        return loaded_cogs, failed_cogs

    for extension_path in ALL_COGS:
        try:
            await bot.load_extension(extension_path)
            loaded_cogs.append(extension_path)
            logger.success(f"Loaded extension: {extension_path}")
        except Exception as e:
            failed_cogs.append((extension_path, str(e)))
            logger.error(f"Failed to load extension {extension_path}: {e}")

    # Report loading summary
    logger.info(
        f"Extension loading complete: {len(loaded_cogs)}/{len(ALL_COGS)} successful"
    )

    if failed_cogs:
        logger.warning("Failed extensions:")
        for cog_name, error in failed_cogs:
            logger.warning(f"  - {cog_name}: {error}")

    return loaded_cogs, failed_cogs


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    logger.info(f"Bot is in {len(bot.guilds)} guilds")

    # List guild for debugging
    for guild in bot.guilds:
        logger.info(f"{guild.name} (id: {guild.id})")

    # Debug: Check what commands are in the tree before syncing
    logger.info(f"Commands in tree before sync: {len(bot.tree.get_commands())}")
    for cmd in bot.tree.get_commands():
        logger.info(f"  - {cmd.name}: {cmd.description}")

    if ENV == "dev" and DEV_GUILD_ID:
        try:
            guild = discord.Object(id=DEV_GUILD_ID)
            # Copy global commands to the dev guild for instant updates
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.success(
                f"Synced {len(synced)} slash commands to dev guild {DEV_GUILD_ID}"
            )

            # Debug: List what was actually synced
            for cmd in synced:
                logger.info(f"  Synced: {cmd.name}")

        except Exception as e:
            logger.error(f"Failed to sync commands to dev guild: {e}")
    else:
        try:
            synced = await bot.tree.sync()
            logger.success(f"Synced {len(synced)} slash commands globally")
        except Exception as e:
            logger.error(f"Failed to sync commands globally: {e}")


# Manual sync command for testing
@bot.command()
@commands.is_owner()
async def sync(ctx, guild_id: int = None):
    """Manually sync slash commands"""
    try:
        if guild_id:
            # Validate server exists and bot is a member
            guild = bot.get_guild(guild_id)
            if not guild:
                await ctx.send(
                    f"Bot is not in server {guild_id} or server doesn't exist"
                )
                return

            guild_obj = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild_obj)
            await ctx.send(f"Synced {len(synced)} slash commands to server {guild_id}")
        else:
            synced = await bot.tree.sync()
            await ctx.send(f"Synced {len(synced)} slash commands globally")
    except Exception as e:
        await ctx.send(f"Failed to sync: {e}")
        logger.error(f"Sync command failed: {e}")


async def graceful_shutdown():
    """Gracefully shutdown the bot"""
    logger.info("Gracefully shutting down...")
    try:
        # Saves any pending data, close connections, etc.
        for cog_name in list(bot.extensions.keys()):
            try:
                await bot.unload_extension(cog_name)
                logger.info(f"Unloaded extension: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to unload extension: {cog_name}: {e}")

        await bot.close()
        logger.info("Bot shutdown complete")
    except asyncio.CancelledError:
        logger.warning(
            "Graceful shutdown was cancelled, possibly due to event loop stopping"
        )
    except Exception as e:
        logger.error(f"Error during graceful_shutdown: {e}")
    finally:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def signal_handler(signum, frame):
    """Handles shutdown signals"""
    logger.info(f"Received signal {signum}")
    asyncio.create_task(graceful_shutdown())


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


async def main():
    await init_db()
    await load_cogs()
    await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
