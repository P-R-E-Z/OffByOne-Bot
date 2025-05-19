# applications.py
import discord
from discord.ext import commands
from discord import app_commands

class Application(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    app_commands.command(name="apply", description="Start the application for advertising access.")
    @app_commands.describe(role_type="Type of role you're applying for")
    async def apply(self, interaction: discord.Interaction, role_type: str):
    await interaction.response.send_message(f"Thanks for applying for {role_type} Check your DM's for further instructions.", ephemeral=True)
    try:
        await interaction.user.send()
        f"Lets start your application for `{role_type}`application.\n(Feature coming soon)"
        )
    except discord.Forbidden:
        await interaction.followup.send("Couldn't DM you. Enable messages from server members", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Application(bot))
