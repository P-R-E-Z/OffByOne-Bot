# Background task to poll linked Discord channels for updates
from discord.ext import commands, tasks


class ChannelPoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.poll_channels.start()

    @tasks.loop(minutes=5)
    async def poll_channels(self):
        # TODO: Poll channels for updates
        pass

    def cog_unload(self):
        self.poll_channels.cancel()


async def setup(bot):
    await bot.add_cog(ChannelPoller(bot))
