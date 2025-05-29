# Lets users enable/disable certain features
from discord.ext import commands


class Toggles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


@commands.command(name="toggle")
async def toggle_feature(self, ctx, feature: str):
    await ctx.send(f"Toggling {feature} (WIP)")


async def setup(bot):
    await bot.add_cog(Toggles(bot))
