# Discord message, channel, and user resolution tools
from discord.app_commands import guilds


def resolve_channel(guild, channel-id):
    return guilds.get_channel(channel_id)

def resolve_user(bot, user_id):
    return bot.get_user(user_id)