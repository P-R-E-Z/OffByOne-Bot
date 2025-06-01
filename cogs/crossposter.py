# Crossposts message to the specified channel using a webhook
from collections import namedtuple
import discord
from discord.ext import commands


class CrossPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="crosspost")
    async def crosspost(self, ctx, message_id: int):
        try:
            original = await ctx.channel.fetch_message(message_id)
            webhook = await ctx.channel.creat_webhook(name="crosspost")
            await webhook.send(
                content=original.content, username=original.author.display_avatar_url
            )
            await webhook.delete()
            await ctx.send("Message posted.", delete_after=5)
        except Exception as e:
            await ctx.send(f"Failed to post: {e}")


async def setup(bot):
    await bot.add_cog(CrossPoster(bot))
