# Sends random meme images from assets/memes
from ctypes import memset
import discord
import os
from discord.ext import commands
import random


class Memes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meme_folder = "assets/memes/"

    @commands.command(name="meme")
    async def _meme(self, ctx):
        try:
            memes = [
                f
                for f in os.listdir(self.meme_folder)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
            ]
            if not memes:
                await ctx.send("No memes found.")
                return
            selected = random.choice(memes)
            await ctx.send(file=discord.File(os.path.join(self.meme_folder, selected)))
        except Exception as e:
            await ctx.send("Error fetching meme: {e}")


async def setup(bot):
    await bot.add_cog(Memes(bot))
