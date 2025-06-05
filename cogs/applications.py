import json
import logging
import time
import asyncio
from typing import Set, Dict, Optional, Any
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import aiosqlite
import discord
from discord import app_commands
from discord.app_commands import guilds
from discord.ext import commands, tasks
from config import DB_PATH

logger = logging.getLogger(__name__)

# Constants
APPLICATION_TIMEOUT = 3600
MINIMUM_ACCOUNT_AGE_DAYS = 7
MAX_RATE_LIMIT_ATTEMPTS = 3
RATE_LIMIT_WINDOW_HOURS = 1
SESSION_CLEANUP_INTERVAL = 30


class ApplicationError(Exception):
    """Custom exception for application-related errors."""

    pass


class ApplicationSession:
    def __init__(self, user_id: int, role_type: str, questions: list, guild_id: int):
        self.user_id = user_id
        self.role_type = role_type
        self.questions = questions
        self.current_question = 0
        self.answers = {}
        self.created_at = time.time()
        self.is_cancelled = False
        self.is_completed = False
        self.guild_id = guild_id

    def add_answer(self, answer: str):
        """Add an answer to the current question."""
        question_key = f"question_{self.current_question + 1}"
        self.answers[question_key] = answer
        self.current_question += 1

    def get_current_question(self) -> Any | None:
        """Get the current question text."""
        if self.current_question < len(self.questions):
            return self.questions[self.current_question]
        return None

    def is_finished(self) -> bool:
        """Check if the application is finished."""
        return self.current_question >= len(self.questions)

    def cancel(self):
        """Cancel the application."""
        self.is_cancelled = True

    def complete(self):
        """Mark the application as completed."""
        self.is_completed = True

    @classmethod
    async def from_database(cls, user_id: int) -> Optional["ApplicationSession"]:
        """Load the application session from the database."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT guild_id, role_type, current_question, answers FROM application_sessions WHERE user_id = ?",
                    (user_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        guild_id, role_type, current_question, answers_json = row
                        # Get questions from role config
                        role_configs = Applications.get_role_configs()
                        questions = role_configs.get(role_type, {}).get("questions", [])

                        session = cls(user_id, role_type, questions, guild_id)
                        session.current_question = current_question
                        session.answers = json.loads(answers_json)
                        return session
                    return None
        except Exception as e:
            logger.error(
                f"Failed to load application session from database for user {user_id}: {e}"
            )
            return None

    async def save_to_database(self):
        """Save the application session to the database."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO application_sessions (user_id, guild_id, role_type, current_question, answers) VALUES (?, ?, ?, ?, ?)",
                    (
                        self.user_id,
                        self.guild_id,
                        self.role_type,
                        self.current_question,
                        json.dumps(self.answers),
                    ),
                )
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to save application session to database for user {self.user_id}: {e}"
            )

    async def delete_from_database(self):
        """Delete the application session from the database."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "DELETE FROM application_sessions WHERE user_id = ?",
                    (self.user_id,),
                )
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to delete application session from database for user {self.user_id}: {e}"
            )


class DatabaseManager:
    """Handles database operations for applications."""

    @staticmethod
    async def cleanup_old_rate_limits():
        """Cleanup old rate limits entries."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(
            hours=RATE_LIMIT_WINDOW_HOURS
        )
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM application_rate_limits WHERE attempt_time < ?",
                (cutoff_time.isoformat(),),
            )
            await db.commit()

    @staticmethod
    async def add_rate_limit_attempt(user_id: int):
        """Add a rate limit attempt."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO application_rate_limits (user_id, attempt_time) VALUES (?, ?)",
                (user_id, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()

    @staticmethod
    async def get_rate_limit_attempts(user_id: int) -> int:
        """Get the current rate limit attempts for a user within the window."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(
            hours=RATE_LIMIT_WINDOW_HOURS
        )
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM application_rate_limits WHERE user_id = ? AND attempt_time < ?",
                (user_id, cutoff_time.isoformat()),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    @staticmethod
    async def batch_application_operations(
        user_id: int, application_id: int, role_type: str, status: str
    ):
        """Batch multiple database operations for application processing."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("BEGIN")
            try:
                # Update application status
                await db.execute(
                    "UPDATE applications SET status = ?WHERE id = ?",
                    (status, application_id),
                )

                # If approved, add to approved roles
                if status == "approved":
                    await db.execute(
                        "INSERT OR REPLACE INTO approved_roles (user_id, role_type) VALUES (?, ?)",
                        (user_id, role_type),
                    )

                # Clean up session data
                await db.execute(
                    "DELETE FROM application_sessions WHERE user_id = ?", (user_id,)
                )

                await db.commit()
            except Exception as e:
                await db.rollback()
                raise e


class ConfigurationValidator:
    """Validates bot configuration for applications."""

    @staticmethod
    async def validate_guild_setup(bot, guild_id: int) -> Dict[str, bool]:
        """Validate that the guild has proper application setup."""
        results = {
            "application_channel": False,
            "role_mappings": False,
            "database_tables": False,
        }

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Check application channel
                async with db.execute(
                    "SELECT channel_id FROM application_channels WHERE guild_id = ?",
                    (guild_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and bot.get_channel(row[0]):
                        results["application_channel"] = True

            # Check role mappings
            async with db.execute(
                "SELECT COUNT(*) FROM role_mappings WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > 0:
                    results["role_mappings"] = True

            # Check database tables exist
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('applications', 'application_channels', 'role_mappings')"
            ) as cursor:
                tables = await cursor.fetchall()
                if len(tables) >= 3:
                    results["database_tables"] = True

        except Exception as e:
            logger.error(f"Error validating guild setup for {guild_id}: {e}")

        return results


async def _check_user_permissions(user: discord.Member) -> bool:
    """Check if user meets basic requirements for applications."""
    account_age_days = (discord.utils.utcnow() - user.created_at).days
    return account_age_days >= 7  # Require 7+ day old accounts


async def _get_application_by_user_id(user_id: int, guild_id: int) -> Optional[dict]:
    """Get pending application by user ID."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, user_id, guild_id, role_type, answers, status FROM applications WHERE user_id = ? AND guild_id = ? AND status = 'completed'",
                (user_id, guild_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "user_id": row[1],
                        "guild_id": row[2],
                        "role_type": row[3],
                        "answers": json.loads(row[4]),
                        "status": row[5],
                    }
    except Exception as e:
        logger.error(f"Error getting application for user {user_id}: {e}")
    return None


def _has_mod_permissions(member: discord.Member) -> bool:
    """Check if user has moderator permissions."""
    if member.guild_permissions.administrator:
        return True

    # Check for moderator-like roles
    mod_role_keywords = ["moderator", "admin", "staff", "mod"]
    return any(
        any(keyword in role.name.lower() for keyword in mod_role_keywords)
        for role in member.roles
    )


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_applications_users: Set[int] = set()
        self.active_sessions: Dict[int, ApplicationSession] = {}

    @staticmethod
    def get_role_configs() -> Dict[str, Dict[str, Any]]:
        """Get role configuration dictionary."""
        return {
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
        return role_type in self.get_role_configs()

    @staticmethod
    async def _check_rate_limit(user_id: int) -> bool:
        """Check if user is rate limited."""
        await DatabaseManager.cleanup_old_rate_limits()
        attempts = await DatabaseManager.get_rate_limit_attempts(user_id)

        if attempts >= MAX_RATE_LIMIT_ATTEMPTS:
            return False

        await DatabaseManager.add_rate_limit_attempt(user_id)
        return True

    async def _get_application_channel(
        self, guild_id: int
    ) -> Optional[discord.TextChannel]:
        """Get the application channel for the given guild."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT channel_id FROM application_channels WHERE guild_id = ?",
                    (guild_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return self.bot.get_channel(row[0])
        except Exception as e:
            logger.error(f"Error getting application channel for guild {guild_id}: {e}")
        return None

    async def _create_application_session(
        self, user: discord.User, role_type: str, guild_id: int
    ) -> ApplicationSession:
        """Create and store new application session."""
        role_configs = self.get_role_configs()
        questions = role_configs[role_type]["questions"]
        session = ApplicationSession(user.id, role_type, questions, guild_id)

        # Store in memory and database
        self.active_sessions[user.id] = session
        await session.save_to_database()

        return session

    async def _send_question_embed(
        self, user: discord.User, session: ApplicationSession
    ):
        """Send a question embed to the user."""
        current_question = session.get_current_question()
        if not current_question:
            return

        role_configs = self.get_role_configs()
        question_num = session.current_question + 1
        total_questions = len(session.questions)

        embed = discord.Embed(
            title=f"{role_configs[session.role_type]['name']} Application",
            description=f"Question {question_num} of {total_questions}:\n\n{current_question}",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text="Reply with your answer. Type 'cancel' to cancel the application."
        )

        await user.send(embed=embed)

    async def _start_application_questions(
        self, user: discord.User, role_type: str, guild_id: int
    ):
        """Start the interactive question flow via DM."""
        try:
            session = await self._create_application_session(user, role_type, guild_id)
            await self._send_question_embed(user, session)
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning(
                f"Failed to start application questions for user {user.id}: {e}"
            )

            # Clean up session if DM fails
            if user.id in self.active_sessions:
                del self.active_sessions[user.id]
            raise

    async def _validate_application_prerequisites(
        self, interaction: discord.Interaction, role_type: str
    ) -> bool:
        """Validate all prerequisites for starting an application."""
        user_id = interaction.user.id

        # Validation checks
        if not self._validate_role_type(role_type):
            raise ApplicationError("Invalid role type selected.")

        if not await self._check_rate_limit(user_id):
            await interaction.response.send_message(
                "You've made too many application attempts recently. Please wait before trying again.",
                ephemeral=True,
            )
            return False

        if user_id in self.pending_applications_users:
            await interaction.response.send_message(
                "You already have an application pending. Please wait for it to be approved or denied.",
                ephemeral=True,
            )
            return False

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
                    return False
        return True

    async def _process_dm_response(self, message: discord.Message):
        """Process a DM response."""
        user_id = message.author.id

        if user_id not in self.active_sessions:
            return

        session = self.active_sessions[user_id]
        content = message.content.strip()

        # Check for cancellation
        if content.lower() == "cancel":
            await self._cancel_application(message.author, session)
            return

        # Add the answer
        session.add_answer(content)

        # Check if there are more questions
        if not session.is_finished():
            # Send next question
            next_question = session.get_current_question()
            question_num = session.current_question + 1
            total_questions = len(session.questions)

            embed = discord.Embed(
                title=f"{self.get_role_configs()[session.role_type]['name']} Application",
                description=f"Question {question_num} of {total_questions}:\n\n{next_question}",
                color=discord.Color.blue(),
            )
            embed.set_footer(
                text="Reply with your answer. Type 'cancel' to cancel the application."
            )

            await message.author.send(embed=embed)
        else:
            # Application completed
            await self._complete_application(message.author, session)

    async def _cancel_application(
        self, user: discord.User, session: ApplicationSession
    ):
        """Cancel an application."""
        try:
            # Update database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE applications SET status = 'cancelled' WHERE user_id = ? AND status = 'pending'",
                    (user.id, session.guild_id),
                )
                await db.commit()

            # Clean up session from database
            await session.delete_from_database()

            # Clean up in-memory data
            if user.id in self.active_sessions:
                del self.active_sessions[user.id]
            if user.id in self.pending_applications_users:
                self.pending_applications_users.remove(user.id)

            embed = discord.Embed(
                title="Application Cancelled",
                description="Your application has been cancelled.",
                color=discord.Color.red(),
            )
            await user.send(embed=embed)

            logger.info(f"Application cancelled for user {user.id}")

        except Exception as e:
            logger.error(f"Error cancelling application for user {user.id}: {e}")

    async def _complete_application(
        self, user: discord.User, session: ApplicationSession
    ):
        """Complete an application and send to review channel."""
        try:
            # Update database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE applications SET answers = ?, status = 'completed' WHERE user_id = ? AND guild_id = ? AND status = 'pending'",
                    (json.dumps(session.answers), user.id, session.guild_id),
                )
                await db.commit()

            # Clean up
            if user.id in self.active_sessions:
                del self.active_sessions[user.id]
            if user.id in self.pending_applications_users:
                self.pending_applications_users.remove(user.id)

            # Send confirmation message to user
            embed = discord.Embed(
                title="Application Submitted",
                description=f"Thank you for submitting your application for {self.get_role_configs()[session.role_type]['name']}. Your application has been submitted and is being reviewed by our team.",
                color=discord.Color.green(),
            )
            await user.send(embed=embed)

            # Send to review channel
            await self._send_to_review_channel(user, session)

            logger.info(
                f"Application completed for user {user.id}, role: {session.role_type}"
            )

        except Exception as e:
            logger.error(f"Error completing application for user {user.id}: {e}")

    async def _send_to_review_channel(
        self, user: discord.User, session: ApplicationSession
    ):
        """Send an application to the review channel."""
        try:
            channel = await self._get_application_channel(session.guild_id)
            if not channel:
                logger.warning(
                    f"No application channel found for guild {session.guild_id}"
                )
                return

            # Create review embed
            embed = discord.Embed(
                title=f"New {self.get_role_configs()[session.role_type]['name']} Application",
                color=discord.Color.orange(),
            )
            embed.add_field(name="User", value=f"{user.mention} ({user})", inline=False)
            embed.add_field(name="User ID", value=str(user.id), inline=True)
            embed.add_field(
                name="Role Type",
                value=self.get_role_configs()[session.role_type]["name"],
                inline=True,
            )
            embed.add_field(
                name="Submitted",
                value=discord.utils.format_dt(datetime.now(timezone.utc)),
                inline=True,
            )

            # Add questions and answers
            for i, question in enumerate(session.questions, 1):
                answer_key = f"question_{i}"
                answer = session.answers.get(answer_key, "No answer provided")
                embed.add_field(name=f"Q{i}: {question}", value=answer, inline=False)

            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text=f"Application ID: {user.id}")

            # Get guild and ping roles
            guild = self.bot.get_guild(session.guild_id)
            ping_roles = []

            if guild:
                # Look for moderator/admin roles to ping
                ping_roles.extend(
                    role.mention
                    for role in guild.roles
                    if any(
                        keyword in role.name.lower()
                        for keyword in ["moderator", "admin", "staff", "mod"]
                    )
                )
            ping_text = " ".join(ping_roles) if ping_roles else ""
            content = (
                f"{ping_text}\n**New application submitted for review!**"
                if ping_text
                else "**New application submitted for review!**"
            )

            await channel.send(content=content, embed=embed)

        except Exception as e:
            logger.error(f"Error sending application to review channel: {e}")

    async def _get_role_for_type(
        self, guild_id: int, role_type: str
    ) -> Optional[discord.Role]:
        """Get the Discord role for a given role type in a guild."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT role_id FROM role_mappings WHERE guild_id = ? AND role_type = ?",
                    (guild_id, role_type),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        if guild := self.bot.get_guild(guild_id):
                            return guild.get_role(row[0])
        except Exception as e:
            logger.error(
                f"Error getting role for type {role_type} in guild {guild_id}: {e}"
            )
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle DM responses."""
        # Ignore bot messages
        if message.author.bot:
            return

        # Only process DMs
        if not isinstance(message.channel, discord.DMChannel):
            return

        # Check if user has active session
        if message.author.id in self.active_sessions:
            await self._process_dm_response(message)

    async def cog_load(self):
        # Load existing sessions from database
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT user_id FROM applications_sessions"
                ) as cursor:
                    async for row in cursor:
                        user_id = row[0]
                        session = await ApplicationSession.from_database(user_id)
                        if session:
                            self.active_sessions[user_id] = session
        except Exception as e:
            logger.error(f"Error loading sessions for user {user_id}: {e}")

        # Populate pending applications from database
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id FROM applications WHERE status = 'pending'"
            ) as cursor:
                async for row in cursor:
                    self.pending_applications_users.add(row[0])
        logger.info(
            f"Loaded {len(self.pending_applications_users)} pending application for user {self.bot.user.id}"
        )

        # Start the cleanup task after everything is loaded
        self.cleanup_expired_applications.start()

    async def cog_unload(self):
        self.cleanup_expired_applications.cancel()

    @commands.command(name="applications_setup")
    @commands.has_permissions(manage_guild=True)
    async def setup_applications_channel(
        self, ctx, channel: discord.TextChannel = None
    ):
        """Set up the channel where completed applications will be sent."""
        if channel is None:
            channel = ctx.channel

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO application_channels (guild_id, channel_id) VALUES (?, ?)",
                    (ctx.guild.id, channel.id),
                )
                await db.commit()

            embed = discord.Embed(
                title="Applications Channel Set",
                description=f"Completed applications will now be sent to {channel.mention}.",
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)
            logger.info(
                f"Applications channel set to {channel.id} for guild {ctx.guild.id}"
            )

        except Exception as e:
            logger.error(f"Error setting up applications channel: {e}")
            await ctx.send(
                "An error occurred while setting up the applications channel."
            )

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
                    "INSERT INTO applications (user_id, guild_id, role_type, answers, status) VALUES (?, ?, ?, ?, ?)",
                    (
                        user_id,
                        interaction.guild_id,
                        role_type,
                        json.dumps({}),
                        "pending",
                    ),
                )
                await db.commit()

            self.pending_applications_users.add(user_id)
            logger.info(
                f"Application created successfully - User: {user_id}, Role: {role_type}"
            )

            role_display_name = (
                self.get_role_configs().get(role_type, {}).get("name", role_type)
            )
            await interaction.response.send_message(
                f"Thanks for applying for {role_display_name}! You will receive a DM from the Bot with your application details shortly.",
                ephemeral=True,
            )

            # Send DM with application questions
            try:
                await self._start_application_questions(
                    interaction.user, role_type, interaction.guild_id
                )
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

    @commands.command(name="setup_role")
    @commands.has_permissions(manage_guild=True)
    async def setup_role_mapping(self, ctx, role_type: str, role: discord.Role):
        """Set up the role mapping for a role type."""
        if not self._validate_role_type(role_type):
            await ctx.send(
                "Invalid role type selected. Valid types: game_server_owner, content_creator, developer."
            )
            return

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO role_mappings (guild_id, role_type, role_id) VALUES (?, ?, ?)",
                    (ctx.guild.id, role_type, role.id),
                )
                await db.commit()

            role_display_name = self.get_role_configs()[role_type]["name"]
            embed = discord.Embed(
                title="Role Mapping Set",
                description=f"{role_display_name} applications will now assign the {role.mention} role.",
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)
            logger.info(
                f"Role mapping set: {role_type} -> {role.id} in guild {ctx.guild.id}"
            )

        except Exception as e:
            logger.error(f"Error setting up role mapping: {e}")
            await ctx.send("An error occurred while setting up the role mapping.")

    @app_commands.command(
        name="accept_application", description="Accept a user's application."
    )
    @app_commands.guild_only()
    @app_commands.describe(user="The user whose application to accept.")
    async def accept_application(
        self, interaction: discord.Interaction, user: discord.Member
    ):
        """Accept a user's application."""

        # Check permissions
        if not _has_mod_permissions(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to accept applications.", ephemeral=True
            )
            return

        try:
            # Get application
            application = await _get_application_by_user_id(
                user.id, interaction.guild_id
            )
            if not application:
                await interaction.response.send_message(
                    f"No pending application found for user {user.mention}.",
                    ephemeral=True,
                )
                return

            # Get the role to assign
            role_to_assign = await self._get_role_for_type(
                interaction.guild_id, application["role_type"]
            )
            if not role_to_assign:
                await interaction.response.send_message(
                    f"No role mapping found for role type {application['role_type']}. Use `!setup_role` to configure role mappings.",
                    ephemeral=True,
                )
                return

            # Assign the role
            await user.add_roles(
                role_to_assign, reason=f"Application accepted by {interaction.user}"
            )

            # Update database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE applications SET status = 'approved' WHERE id = ?",
                    (application["id"],),
                )
                await db.execute(
                    "INSERT OR REPLACE INTO approved_roles (user_id, role_type) VALUES (?, ?)",
                    (user.id, application["role_type"]),
                )
                await db.commit()

            # Remove from pending users
            if user.id in self.pending_applications_users:
                self.pending_applications_users.remove(user.id)

            role_display_name = self.get_role_configs()[application["role_type"]][
                "name"
            ]

            # Send DM to user
            try:
                embed = discord.Embed(
                    title="Application Approved",
                    description=f"Your application for **{role_display_name}** has been accepted and the role has been applied to you.",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Next Steps",
                    value="Visit #advertising-information to learn what commands you can use now and general role-specific information.",
                    inline=False,
                )
                embed.set_footer(
                    text=f"Welcome to the {role_display_name} advertising portion of the server!"
                )
                await user.send(embed=embed)
            except discord.Forbidden:
                logger.warning(
                    f"Could not DM user {user.id} about application approval."
                )

            # Respond to moderator
            embed = discord.Embed(
                title="Application Approved",
                description=f"Successfully approved {user.mention}'s application for **{role_display_name}** and assigned the {role_to_assign.mention} role.",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed)

            logger.info(
                f"Application approved: User {user.id}, Role: {application['role_type']}, Approved by: {interaction.user.id}"
            )

        except Exception as e:
            logger.error(f"Error accepting application: {e}")
            await interaction.response.send_message(
                "An error occurred while processing the application.", ephemeral=True
            )

    @app_commands.command(
        name="deny_application", description="Deny a user's application."
    )
    @app_commands.guild_only()
    @app_commands.describe(
        user="The user whose application to deny.",
        reason="The reason for denying the application (optional).",
    )
    async def deny_application(
        self, interaction: discord.Interaction, user: discord.Member, reason: str = None
    ):
        """Deny a user's application."""

        # Check permissions
        if not _has_mod_permissions(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to deny applications.", ephemeral=True
            )
            return

        try:
            # Get the application
            application = await _get_application_by_user_id(
                user.id, interaction.guild_id
            )
            if not application:
                await interaction.response.send_message(
                    f"No pending application found for user {user.mention}.",
                    ephemeral=True,
                )
                return

            # Update database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE applications SET status = 'denied' WHERE id = ?",
                    (application["id"],),
                )
                await db.commit()

            # Remove from pending users
            if user.id in self.pending_applications_users:
                self.pending_applications_users.remove(user.id)

            role_display_name = self.get_role_configs()[application["role_type"]][
                "name"
            ]

            # Send DM to user
            try:
                embed = discord.Embed(
                    title="Application Update",
                    description=f"Your application for **{role_display_name}** has been denied.",
                    color=discord.Color.red(),
                )
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(
                    name="Reapplying",
                    value="You may reapply in the future. Please consider the feedback provided.",
                    inline=False,
                )
                await user.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user.id} about application denial.")

            # Respond to moderator
            embed = discord.Embed(
                title="Application Denied",
                description=f"Successfully denied {user.mention}'s application for **{role_display_name}**.",
                color=discord.Color.red(),
            )
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)

            logger.info(
                f"Application denied: User {user.id}, Role: {application['role_type']}, Denied by: {interaction.user.id}"
            )

        except Exception as e:
            logger.error(f"Error denying application: {e}")
            await interaction.response.send_message(
                "An error occurred while processing the application.", ephemeral=True
            )

    @cleanup_expired_applications.before_loop
    async def before_cleanup_task(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Applications(bot))
