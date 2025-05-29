# Moderation tools
import discord
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        await member.kick(reason=reason)
        await ctx.send(f"{member.name} was kicked.")

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        await member.ban(reason=reason)
        await ctx.send(f"{member.name} was banned.")

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, member):
        await ctx.guild.unban(member)
        await ctx.send(f"{member} was unbanned.")

    @commands.command(name="mute")
    @commands.has_permissions(mute_members=True)
    async def mute(self, ctx, member: discord.Member, *, reason=None):
        await member.send(f"{member.name} was muted.")
        await ctx.send(f"{member.name} was muted.")

    @commands.command(name="unmute")
    @commands.has_permissions(mute_members=True)
    async def unmute(self, ctx, member: discord.Member, *, reason=None):
        await member.send(f"{member.name} was unmuted.")
        await ctx.send(f"{member.name} was unmuted.")

    @commands.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount=5):
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"{amount} messages deleted.")


async def setup(bot):
    await bot.add_cog(Moderation(bot))
