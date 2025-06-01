# DB schema definitions for OffByOne
# Starter SQL logic via aiosqlite

CREATE_APPLICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role_type TEXT NOT NULL,
    answers TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_APPROVED_ROLES_TABLE = """
CREATE TABLE IF NOT EXISTS approved_roles (
    user_id INTEGER NOT NULL,
    role_type TEXT NOT NULL,
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_type)
);
"""

CREATE_REPO_HOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS rep_hooks (
    user_id INTEGER NOT NULL,
    repo_url TEXT NOT NULL,
    forum_post_id TEXT NOT NULL,
    track_new_repos BOOLEAN DEFAULT 1,
    track_commits BOOLEAN DEFAULT 1,
    PRIMARY KEY (user_id, repo_url)
);
"""

CREATE_CHANNEL_HOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS channel_hooks (
    user_id INTEGER NOT NULL,
    discord_channel_id INTEGER NOT NULL,
    forum_post_id TEXT NOT NULL,
    PRIMARY KEY (user_id, discord_channel_id)
);
"""

CREATE_TOGGLES_TABLE = """
CREATE TABLE IF NOT EXISTS user_toggles (
    user_id INTEGER NOT NULL,
    feature TEXT NOT NULL,
    value BOOLEAN DEFAULT 1,
    PRIMARY KEY (user_id, feature)
);
"""

CREATE_SERVER_CONFIGS_TABLE = """
CREATE TABLE IF NOT EXISTS server_configs (
    guild_id INTEGER PRIMARY KEY,
    application_channel_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
