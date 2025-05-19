# Alerts mods to unanswered applications
from discord.ext import tasks, commands


class AppNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.notify_pending_apps.start()

    @tasks.loop(hours=1)
    async def notify_pending_apps(self):
        # TODO: Notify mods of pending applications
        pass

    def cog_unload(self):
        self.notify_pending_apps.cancel()

    async def setup(bot):
        await bot.add_cog(AppNotifier(bot))
