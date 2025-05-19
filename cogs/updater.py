# Edits forum posts or sends replies
import os
import discord
from discord.ext import commands


class Updater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="update")
    async def update_forum_post(self, ctx):
        await ctx.send("Forum post updating WIP")


async def setup(bot):
    await bot.add_cog(UpdaterCog(bot))
