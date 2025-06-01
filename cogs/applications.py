import json
import logging
import time
import asyncio
from typing import Set
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import DB_PATH

logger = logging.getLogger(__name__)

APPLICATION_TIMEOUT = 3600


class ApplicationError(Exception):
    """Custom exception for application-related errors."""

    pass


class ApplicationSession:
    def __init__(self, user_id: int, role_type: str, questions: list):
        self.user_id = user_id
        self.role_type = role_type
        self.questions = questions
        self.current_question = 0
        self.answers = {}
        self.created_at = time.time()


async def _check_user_permissions(user: discord.Member) -> bool:
    """Check if user meets basic requirements for applications."""
    account_age_days = (discord.utils.utcnow() - user.created_at).days
    return account_age_days >= 7  # Require 7+ day old accounts


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_applications_users: Set[int] = set()
        self.application_attempts = defaultdict(list)  # Track attempts per user
        self.role_configs = {
            "game_server_owner": {
                "name": "Game Server Owner",
                "questions": [
                    "Are you the owner of the server?",
                    "What is your server name?",
                    "Link to your server",
                    "What game is your server for?",
                ],
            },
            "content_creator": {
                "name": "Content Creator",
                "questions": [
                    "What type of content are you creating?",
                    "What is your content name?",
                    "How often do you post?",
                    "Link to your content channels/pages",
                ],
            },
            "developer": {
                "name": "Developer",
                "questions": [
                    "How long have you been a developer?",
                    "What type of projects do you work?",
                    "Would you like the Bot to track your repos?",
                    "Link to sites you host your repos on",
                ],
            },
        }

    def _validate_role_type(self, role_type: str) -> bool:
        """Validate that the role_type is one of the allowed values."""
        return role_type in self.role_configs

    def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is rate limited (max 3 attempts per hour)."""
        now = datetime.now(timezone.utc)
        user_attempts = self.application_attempts[user_id]

        # Remove attempts older than 1 hour
        user_attempts[:] = [
            attempt for attempt in user_attempts if now - attempt < timedelta(hours=1)
        ]

        if len(user_attempts) >= 3:
            return False

        user_attempts.append(now)
        return True

    async def _start_application_questions(self, user: discord.User, role_type: str):
        """Start the interactive question flow via DM."""
        questions = self.role_configs[role_type]["questions"]
        session = ApplicationSession(user.id, role_type, questions)

        try:
            embed = discord.Embed(
                title=f"{self.role_configs[role_type]['name']} Application",
                description=f"Question 1 of {len(questions)}:\n\n{questions[0]}",
                color=discord.Color.blue(),
            )
            embed.set_footer(
                text="Reply with your answer. Type 'cancel' to cancel the application."
            )

            await user.send(embed=embed)
            # Store session for handling responses
            # This would require implementing a message listener for DM responses

        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning(
                f"Failed to start application questions for user {user.id}: {e}"
            )
            raise

    async def cog_load(self):
        # Populate pending applications from database
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id FROM applications WHERE status = 'pending'"
            ) as cursor:
                async for row in cursor:
                    self.pending_applications_users.add(row[0])
        logger.info(
            f"Loaded {len(self.pending_applications_users)} pending applications."
        )

        # Start the cleanup task after everything is loaded
        self.cleanup_expired_applications.start()

    async def cog_unload(self):
        self.cleanup_expired_applications.cancel()

    @app_commands.command(
        name="apply", description="Start the application for advertising access roles."
    )
    @app_commands.guild_only()
    @app_commands.describe(role_type="Type of role you're applying for.")
    @app_commands.choices(
        role_type=[
            app_commands.Choice(name="Game Server Owner", value="game_server_owner"),
            app_commands.Choice(name="Content Creator", value="content_creator"),
            app_commands.Choice(name="Developer", value="developer"),
        ]
    )
    async def apply(self, interaction: discord.Interaction, role_type: str):
        user_id = interaction.user.id
        logger.info(
            f"Application started - User: {user_id}, Role: {role_type}, Guild: {interaction.guild_id}"
        )

        try:
            # Validation
            if not self._validate_role_type(role_type):
                raise ApplicationError("Invalid role type selected.")

            if not self._check_rate_limit(user_id):
                await interaction.response.send_message(
                    "You've made too many application attempts recently. Please wait before trying again.",
                    ephemeral=True,
                )
                return

            if not await _check_user_permissions(interaction.user):
                await interaction.response.send_message(
                    "Your account doesn't meet the minimum requirements for applications.",
                    ephemeral=True,
                )
                return

            if user_id in self.pending_applications_users:
                await interaction.response.send_message(
                    "You already have an application pending. Please wait for it to be approved or denied.",
                    ephemeral=True,
                )
                return

            # Double check with DB in case in-memory is out of sync
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT id FROM applications WHERE user_id = ? AND status = 'pending'",
                    (user_id,),
                ) as cursor:
                    existing_app = await cursor.fetchone()
                    if existing_app:
                        self.pending_applications_users.add(user_id)
                        await interaction.response.send_message(
                            "You already have an application pending. Please wait for it to be approved or denied.",
                            ephemeral=True,
                        )
                        return

            # Add to database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO applications (user_id, role_type, answers, status) VALUES (?, ?, ?, ?)",
                    (user_id, role_type, json.dumps({}), "pending"),
                )
                await db.commit()

            self.pending_applications_users.add(user_id)
            logger.info(
                f"Application created successfully - User: {user_id}, Role: {role_type}"
            )

            role_display_name = self.role_configs.get(role_type, {}).get(
                "name", role_type
            )
            await interaction.response.send_message(
                f"Thanks for applying for {role_display_name}! You will receive a DM from the Bot with your application details shortly.",
                ephemeral=True,
            )

            # Send DM with application questions
            try:
                await self._start_application_questions(interaction.user, role_type)
            except (discord.Forbidden, discord.HTTPException):
                await interaction.followup.send(
                    "Couldn't send you a DM. Please check your privacy settings. Your application is pending.",
                    ephemeral=True,
                )
                logger.warning(
                    f"Failed to DM user {interaction.user} (ID: {user_id}) - DMs likely disabled."
                )

        except ApplicationError as e:
            await interaction.response.send_message(
                f"Application error: {e}", ephemeral=True
            )
        except aiosqlite.Error as e:
            logger.error(f"Database error in apply command: {e}")
            try:
                await interaction.response.send_message(
                    "A database error occurred. Please try again later.", ephemeral=True
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "A database error occurred. Please try again later.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Unexpected error in apply command: {e}")
            try:
                await interaction.response.send_message(
                    "An unexpected error occurred. Please contact an administrator.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "An unexpected error occurred. Please contact an administrator.",
                    ephemeral=True,
                )

    @tasks.loop(minutes=30)
    async def cleanup_expired_applications(self):
        logger.info("Running cleanup task for expired applications...")
        current_time = time.time()
        expired_user_ids_processed = []
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT id, user_id, submitted_at FROM applications WHERE status = 'pending'"
                ) as cursor:
                    rows_to_check = await cursor.fetchall()

                for app_id, user_id, submitted_at_str in rows_to_check:
                    try:
                        submitted_timestamp = time.mktime(
                            time.strptime(submitted_at_str, "%Y-%m-%d %H:%M:%S")
                        )
                        if (current_time - submitted_timestamp) > APPLICATION_TIMEOUT:
                            await db.execute(
                                "UPDATE applications SET status = 'expired' WHERE id = ?",
                                (app_id,),
                            )
                            logger.info(
                                f"Application ID {app_id} for user {user_id} has expired. Status updated to 'expired'."
                            )
                            if user_id in self.pending_applications_users:
                                self.pending_applications_users.remove(user_id)
                            expired_user_ids_processed.append(user_id)
                    except ValueError as e:
                        logger.error(
                            f"Could not parse timestamp '{submitted_at_str}' for app_id {app_id}: {e}"
                        )

                if expired_user_ids_processed:
                    await db.commit()
                logger.info(
                    f"Expired applications cleanup finished. Processed {len(expired_user_ids_processed)} expirations."
                )
        except Exception as e:
            logger.error(f"Error in cleanup_expired_applications_task: {e}")

    @cleanup_expired_applications.before_loop
    async def before_cleanup_task(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Applications(bot))
