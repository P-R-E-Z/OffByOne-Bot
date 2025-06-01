# Command interface for linking user channels, repos, socials to update targets
from discord.ext import commands


class Hooks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


@commands.command(name="Hook")
async def _hook(self, ctx):
    await ctx.send("Hooking not working yet womp womp")


async def setup(bot):
    await bot.add_cog(Hooks(bot))
