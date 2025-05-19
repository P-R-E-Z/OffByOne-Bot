# User toggles for content updates
import discord
from discord.ext import commands


class Toggle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="toggle")
    async def toggle_feature(self, ctx, feature: str):
        await ctx.send(f"Toggling `{feature}` for you. (WIP)")


async def setup(bot):
    await bot.add_cog(ToggleCog(bot))
