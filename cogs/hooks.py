# Hook repo, Discord channel, and social links
import discord
import discord.ext.commands


class Hooks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="hook")
    async def hook_command(self, ctx):
        await ctx.send("Hook repo WIP")


async def setup(bot):
    await bot.add_cog(Hooks(bot))
