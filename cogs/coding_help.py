# Provides basic coding assistance to users
import discord
from discord.ext import commands


class CodingHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="syntax")
    async def syntax(self, ctx, language: str, *, topic: str):
        await ctx.send(f"```{language}\n{topic}\n``` (WIP)")

    @commands.command(name="concept")
    async def concept_explainer(self, ctx, *, concept: str):
        await ctx.send(f"```{concept}```")


async def setup(bot):
    await bot.add_cog(CodingHelp(bot))
