# Discord channel/user/message utilities
import requests
import os


def resolve_channel(guild, channel_id):
    return guild.get_channel(channel_id)


def resolve_user(bot, user_id):
    return bot.get_user(user_id)
