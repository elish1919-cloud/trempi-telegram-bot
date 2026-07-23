"""
Shared pytest fixtures for the Trempi test suite.

Sets dummy env vars *before* bot.py / database.py are imported anywhere, so the
test suite never needs a real .env file or a live MongoDB / Telegram connection.
`database.py` opens a MongoClient at import time (lazy connection, but it still
requires MONGO_URI to be set or it raises), so this must run at collection time.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("BOT_TOKEN", "123456789:TEST-TOKEN-not-a-real-secret")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

# test_mongo.py and test_geo.py are standalone manual scripts (not pytest suites) that
# run real network/DB side effects at import time - test_mongo.py seeds the LIVE MongoDB
# with fake rides just by being imported. Keep pytest from collecting them.
collect_ignore = ["test_mongo.py", "test_geo.py"]

import bot  # noqa: E402  (import after env vars are set)


@pytest.fixture
def isolated_users_file(tmp_path, monkeypatch):
    """Point bot.USERS_FILE at a throwaway file so tests never touch the real users.json."""
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(bot, "USERS_FILE", str(users_path))
    return str(users_path)


def make_user(user_id=111, first_name="נועה", username=None):
    user = MagicMock()
    user.id = user_id
    user.first_name = first_name
    user.username = username
    return user


def make_callback_update(data, user_id=111, first_name="נועה"):
    """Build a mocked Update carrying a callback_query, matching what CallbackQueryHandler passes in."""
    user = make_user(user_id, first_name)

    query = MagicMock()
    query.data = data
    query.from_user = user
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    update.effective_user = user
    return update


def make_message_update(text, user_id=111, first_name="נועה"):
    """Build a mocked Update carrying a plain text message, matching what MessageHandler passes in."""
    user = make_user(user_id, first_name)

    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.message = message
    update.effective_user = user
    update.callback_query = None
    update.effective_message = message
    return update


class FakeContext:
    """Minimal stand-in for telegram.ext.ContextTypes.DEFAULT_TYPE - just the two dicts handlers use."""

    def __init__(self):
        self.user_data = {}
        self.chat_data = {}


@pytest.fixture
def fake_context():
    return FakeContext()
