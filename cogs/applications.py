import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Dict, Set
import json
import aiofiles
import time
import logging

logger = logging.getLogger(__name__)


async def load_application_state(self):
    # Load from database on cog initialization
    pass


async def save_application_state(self):
    # Save to a database on cog shutdown
    pass


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_applications: Set[int] = set()
        self.application_data: Dict[int, str] = {}
        self.role_configs = {
            "game_server_owner": {
                "name": "Game Server Owner",
                "description": "Advertise your game servers in this server.",
            },
            "content_creator": {
                "name": "Content Creator",
                "description": "Advertise your content in this server.",
            },
            "developer": {
                "name": "Developer",
                "description": "Advertise your repo's in this server.",
            },
        }

    @app_commands.command(
        name="apply", description="Start the application for advertising access."
    )
    @app_commands.guild_only()
    async def apply(self, interaction: discord.Interaction, role_type: str):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

    @app_commands.describe(role_type="Type of role you're applying for")
    @app_commands.choices(
        role_type=[
            app_commands.Choice(name="Game Server Owner", value="game_server_owner"),
            app_commands.Choice(name="Content Creator", value="content_creator"),
            app_commands.Choice(name="Developer", value="developer"),
        ]
    )
    async def apply(self, interaction: discord.Interaction, role_type: str):
        if interaction.user.id in self.pending_applications:
            await interaction.response.send_message(
                "You already have a pending application.", ephemeral=True
            )
            return

        self.pending_applications.add(interaction.user.id)
        await interaction.response.send_message(
            f"Thanks for applying for {role_type} Check your DM's for further instructions.",
            ephemeral=True,
        )

        try:
            await interaction.user.send(
                f"Lets start your {role_type} application for advertising access (WIP)."
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.followup.send(
                "Couldn't send you a DM. Please check your privacy settings.",
                ephemeral=True,
            )
            logger.warning(f"Failed to DM user {interaction.user} - DMs disabled")


# Timeout Handling
APPLICATION_TIMEOUT = 3600  # 1 Hour


async def cleanup_expired_applications(self):
    current_time = time.time()
    expired_users = [
        user_id
        for user_id, data in self.application_data.items()
        if current_time - data.get("timestamp", 0) > APPLICATION_TIMEOUT
    ]
    for user_id in expired_users:
        self.remove_pending_application(user_id)


async def setup(bot):
    await bot.add_cog(Applications(bot))
