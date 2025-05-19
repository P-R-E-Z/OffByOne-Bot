# GitHub/GitLab polling logic
from discord.ext import tasks, commands


class RepoPoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.poll_repos.start()

    @tasks.loop(minutes=5)
    async def poll_repos(selfself):
        # TODO: Poll GitHub/GitLab repos for updates
        pass

    def cog_unload(self):
        self.poll_repos.cancel()


async def setup(bot):
    await bot.add_cog(RepoPoller(bot))
