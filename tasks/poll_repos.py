# Background task to poll linked GitHub/GitLab repos
from discord.ext import commands, tasks


class RepoPoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.poll_repos.start()

    @tasks.loop(minutes=5)
    async def poll_repos(self):
        # TODO: Poll repos for updates
        pass

    def cog_unload(self):
        self.poll_repos.cancel()


async def setup(bot):
    await bot.add_cog(RepoPoller(bot))
