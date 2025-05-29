# Handles editing or replying forum posts when updates happen
from discord.ext import commands


class Updater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


@commands.command(name="update")
async def update(self, ctx):
    await ctx.send("Forum post updating (WIP)")


async def setup(bot):
    await bot.add_cog(Updater(bot))
