import discord
from discord.ext import commands
from discord import app_commands, Interaction


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_applications = set()  # Track users with pending applications

    @app_commands.command(
        name="apply", description="Start the application for advertising access."
    )
    @app_commands.describe(role_type="Type of role you're applying for")
    @app_commands.choices(
        role_type=[
            app_commands.Choice(name="Advertiser", value="advertiser"),
            app_commands.Choice(name="Partner", value="partner"),
            app_commands.Choice(name="Sponsor", value="sponsor"),
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


async def setup(bot):
    await bot.add_cog(Applications(bot))
