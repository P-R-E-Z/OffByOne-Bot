# Notifies Mods of pending applications
from discord.ext import commands, tasks


class AppNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.notify_pending_apps.start()

    @tasks.loop(hours=1)
    async def notify_pending_apps(self):
        # TODO: Query database for pending applications
        pass

    def cog_unload(self):
        self.notify_pending_apps.cancel()


async def setup(bot):
    await bot.add_cog(AppNotifier(bot))
