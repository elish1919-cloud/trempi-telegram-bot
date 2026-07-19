"""
Tests for ride actions that aren't pure matching logic:
- cancel(): aborting an in-progress conversation (ride creation / search / registration)
- role_button(): switching a user's role between driver and passenger
- handle_join_ride(): joining an open ride, and being blocked from joining a ride
  that was already taken (duplicate-join prevention)

handle_join_ride() previously referenced two undefined names (ride_id,
fallback_message) and never checked the ride's status before replying "success" -
meaning every real join click crashed, and nothing actually stopped two users
from both being told they'd joined the same ride. It was fixed to reuse the
already-correct status-check pattern that existed in the (unused) browse_join()
function. These tests cover the fixed behavior.
"""
import pytest
from telegram.ext import ConversationHandler

import bot
from conftest import make_callback_update, make_message_update, FakeContext


class TestRideCancellation:
    """cancel() is the fallback for /cancel during any multi-step conversation."""

    async def test_cancel_clears_in_progress_ride_data(self, fake_context):
        fake_context.user_data["ride_from"] = "תל אביב"
        fake_context.user_data["ride_to"] = "ירושלים"
        update = make_message_update("/cancel")

        result = await bot.cancel(update, fake_context)

        assert result == ConversationHandler.END
        assert "ride_from" not in fake_context.user_data
        assert "ride_to" not in fake_context.user_data

    async def test_cancel_sends_confirmation_message(self, fake_context):
        update = make_message_update("/cancel")

        await bot.cancel(update, fake_context)

        update.message.reply_text.assert_awaited_once()
        assert "בוטל" in update.message.reply_text.call_args.args[0]

    async def test_cancel_with_no_pending_data_does_not_error(self, fake_context):
        # user_data is already empty - pop() with a default must not raise
        result = await bot.cancel(make_message_update("/cancel"), fake_context)
        assert result == ConversationHandler.END


class TestRoleSwitching:
    """set_user_role()/get_user() back the role_button() handler with users.json."""

    def test_set_user_role_persists_and_is_read_back(self, isolated_users_file):
        bot._save_json_list(bot.USERS_FILE, [{"telegram_id": 555, "role": None}])

        bot.set_user_role(555, "driver")
        assert bot.get_user(555)["role"] == "driver"

        bot.set_user_role(555, "passenger")
        assert bot.get_user(555)["role"] == "passenger"

    def test_set_user_role_does_not_affect_other_users(self, isolated_users_file):
        bot._save_json_list(
            bot.USERS_FILE,
            [{"telegram_id": 555, "role": "driver"}, {"telegram_id": 777, "role": "passenger"}],
        )

        bot.set_user_role(555, "passenger")

        assert bot.get_user(555)["role"] == "passenger"
        assert bot.get_user(777)["role"] == "passenger"  # unchanged

    async def test_role_button_switches_driver_to_passenger(self, isolated_users_file, fake_context):
        bot._save_json_list(bot.USERS_FILE, [{"telegram_id": 555, "first_name": "דנה", "role": None}])

        await bot.role_button(make_callback_update("role_driver", user_id=555), fake_context)
        assert bot.get_user(555)["role"] == "driver"

        await bot.role_button(make_callback_update("role_passenger", user_id=555), fake_context)
        assert bot.get_user(555)["role"] == "passenger"


def make_open_ride(ride_id, **overrides):
    ride = {
        "_id": ride_id,
        "status": "open",
        "from": "תל אביב",
        "to": "אוניברסיטת בר אילן",
        "when": "18:00",
        "driver_phone": None,
        "driver_name": None,
    }
    ride.update(overrides)
    return ride


class FakeRideStore:
    """Stand-in for the Mongo-backed find_ride/update_ride pair, used to verify
    that a ride can only ever transition from 'open' to 'picked' once."""

    def __init__(self, *rides):
        self.rides = {r["_id"]: dict(r) for r in rides}
        self.update_calls = 0

    def find_ride(self, ride_id):
        ride = self.rides.get(ride_id)
        return dict(ride) if ride else None

    def update_ride(self, ride_id, updates):
        self.update_calls += 1
        ride = self.rides.get(ride_id)
        if not ride or ride.get("status") != "open":
            return False
        ride.update(updates)
        return True


class TestJoinRideDuplicatePrevention:
    async def test_joining_an_open_ride_succeeds(self, fake_context, monkeypatch):
        store = FakeRideStore(make_open_ride("ride1"))
        monkeypatch.setattr(bot, "find_ride", store.find_ride)
        monkeypatch.setattr(bot, "update_ride", store.update_ride)

        update = make_callback_update("join_ride1", user_id=111)
        await bot.handle_join_ride(update, fake_context)

        assert store.rides["ride1"]["status"] == "picked"
        assert store.rides["ride1"]["picked_by"] == 111
        update.callback_query.message.reply_text.assert_awaited_once()

    async def test_second_user_cannot_join_already_picked_ride(self, fake_context, monkeypatch):
        store = FakeRideStore(make_open_ride("ride1"))
        monkeypatch.setattr(bot, "find_ride", store.find_ride)
        monkeypatch.setattr(bot, "update_ride", store.update_ride)

        first = make_callback_update("join_ride1", user_id=111)
        await bot.handle_join_ride(first, fake_context)

        second = make_callback_update("join_ride1", user_id=222)
        await bot.handle_join_ride(second, fake_context)

        # the ride is still attributed to the first user, not overwritten by the second
        assert store.rides["ride1"]["picked_by"] == 111
        second_reply = second.callback_query.message.reply_text.call_args.args[0]
        assert "מישהו אחר" in second_reply

    async def test_joining_already_picked_ride_does_not_call_update(self, fake_context, monkeypatch):
        store = FakeRideStore(make_open_ride("ride1", status="picked", picked_by=111))
        monkeypatch.setattr(bot, "find_ride", store.find_ride)
        monkeypatch.setattr(bot, "update_ride", store.update_ride)

        update = make_callback_update("join_ride1", user_id=222)
        await bot.handle_join_ride(update, fake_context)

        assert store.update_calls == 0
        assert store.rides["ride1"]["picked_by"] == 111

    async def test_join_nonexistent_ride_shows_fallback_message(self, fake_context, monkeypatch):
        store = FakeRideStore()  # empty
        monkeypatch.setattr(bot, "find_ride", store.find_ride)
        monkeypatch.setattr(bot, "update_ride", store.update_ride)

        update = make_callback_update("join_does_not_exist", user_id=111)
        await bot.handle_join_ride(update, fake_context)

        reply = update.callback_query.message.reply_text.call_args.args[0]
        assert "מישהו אחר" in reply

    async def test_join_includes_driver_phone_when_available(self, fake_context, monkeypatch):
        store = FakeRideStore(make_open_ride("ride1", driver_phone="0501234567", driver_name="יוסי"))
        monkeypatch.setattr(bot, "find_ride", store.find_ride)
        monkeypatch.setattr(bot, "update_ride", store.update_ride)

        update = make_callback_update("join_ride1", user_id=111)
        await bot.handle_join_ride(update, fake_context)

        reply = update.callback_query.message.reply_text.call_args.args[0]
        assert "0501234567" in reply
        assert "יוסי" in reply
