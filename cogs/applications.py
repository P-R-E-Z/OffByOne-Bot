# Handles /apply command & application DM logic
import discord
from discord.ext import commands
from discord import app_commands
from discord import Interaction

print("Using Interaction from:", Interaction.__module__)


@app_commands.command(name="test")
async def test_cmd(self, interaction: Interaction):
    await interaction.response.send_message("Test command executed.")


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


@app_commands.command(
    name="apply", description="Start application for advertising access"
)
@app_commands.describe(role_type="Role you're applying for")
async def apply(self, interaction: Interaction, role_type: str):
    await interaction.response.send_message(
        f"Thanks for applying for {role_type}. Check your DMs for the application.",
        ephemeral=True,
    )

    try:
        await interaction.user.send(
            f"Lets start your {role_type} application for advertising access (WIP)."
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "Couldn't DM you. Enable messages from server members.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Applications(bot))
