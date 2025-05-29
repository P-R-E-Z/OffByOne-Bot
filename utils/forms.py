# Collects user answers from DMs and returns them as lists
import discord
from typing import Lists, Optional


async def send_dm_form(user, role_type):
    questions = ["What role are you applying for?"]
    if role_type == "advertiser":
        questions = ["Are you the owner"]
    answers = []

    for q in questions:
        try:
            await user.send(q)

            def check(m):
                return m.author == user and isinstance(m.channel, discord.DMchannel)

            msg = await user.bot.wait_for("message", check=check, timeout=120)
            answers.append(msg.content)
        except Exception as e:
            await user.send("There was an error processing your application.")
    return None
