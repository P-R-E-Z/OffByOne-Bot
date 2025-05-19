# DM form/question logic
import os
import discord_hooks

async def send_dm_form(user, role_type):
    # Placeholder for DM form logic
    questions = [
        "What do you want you want to advertise?"
    ]
    answers = []

    for q in questions:
        try:
            await user.send(q)
            def check(m):
                return m.author == user and isinstance(m.channel, discord.channel)

            msg = await user.bot.wait_for("message", check=check, timeout=120)
            answers.append(msg.content)
        except.Exception as e:
            await user.send("There was an error processing your application.")
            return None
    return answers