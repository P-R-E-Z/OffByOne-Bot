# Role check utils and logic to assign advertising roles
import discord
from discord.ext import commands


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def has_verified_role(self, member: discord.Member, role_name: str) -> bool:
        return any(role.name == role_name for role in member.roles)


async def setup(bot):
    await bot.add_cog(Roles(bot))
