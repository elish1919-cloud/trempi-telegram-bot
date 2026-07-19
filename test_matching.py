"""
Ride-matching tests: Haversine distance, FLEX time-window matching, and the
combined "no rides match" scenario, all driven through open_search_flex()
(the handler wired to the SEARCH_FLEX conversation state in main()).

The MongoDB layer (get_open_rides_by_role_from_mongo) and user lookup
(get_user) are monkeypatched with in-memory fixtures, so these tests never
touch a real database. Real-world coordinates are reused from test_mongo.py
so the distances are meaningful, not arbitrary.
"""
import pytest
from telegram.ext import ConversationHandler

import bot
from conftest import make_callback_update

# Real-world coordinates (same points used in test_mongo.py's fake_rides)
COORDS_TA = (32.0853, 34.7818)   # תל אביב
COORDS_BI = (32.0693, 34.8433)   # אוניברסיטת בר אילן - ~6km from Tel Aviv center
COORDS_ME = (31.9312, 35.0114)   # מודיעין עילית - ~27.6km from Tel Aviv center
COORDS_TA_NEARBY = (32.09, 34.79)  # ~0.9km from COORDS_TA - within MAX_PICKUP_DISTANCE_KM


def make_ride(ride_id, from_coords, to_coords, when, created_at="2026-01-01T08:00:00"):
    return {
        "_id": ride_id,
        "role": "driver",
        "from": "מוצא",
        "from_coords": list(from_coords),
        "to": "יעד",
        "to_coords": list(to_coords),
        "when": when,
        "status": "open",
        "created_at": created_at,
    }


class TestDistanceKm:
    """Direct unit tests of the Haversine distance_km() function."""

    def test_same_point_is_zero_distance(self):
        assert bot.distance_km(COORDS_TA, COORDS_TA) == pytest.approx(0.0, abs=1e-6)

    def test_known_real_world_distance_tel_aviv_to_bar_ilan(self):
        # ~6.06km, computed independently with the standard Haversine formula
        assert bot.distance_km(COORDS_TA, COORDS_BI) == pytest.approx(6.06, abs=0.1)

    def test_known_real_world_distance_tel_aviv_to_modiin_illit(self):
        # ~27.6km, well beyond MAX_PICKUP_DISTANCE_KM
        assert bot.distance_km(COORDS_TA, COORDS_ME) == pytest.approx(27.6, abs=0.2)

    def test_nearby_point_is_within_max_pickup_distance(self):
        d = bot.distance_km(COORDS_TA, COORDS_TA_NEARBY)
        assert d < bot.MAX_PICKUP_DISTANCE_KM

    def test_far_point_exceeds_max_pickup_distance(self):
        d = bot.distance_km(COORDS_TA, COORDS_ME)
        assert d > bot.MAX_PICKUP_DISTANCE_KM

    def test_distance_is_symmetric(self):
        assert bot.distance_km(COORDS_TA, COORDS_BI) == pytest.approx(
            bot.distance_km(COORDS_BI, COORDS_TA), abs=1e-9
        )


@pytest.fixture
def passenger_user(monkeypatch):
    """A registered passenger, so open_search_flex searches for driver rides."""
    monkeypatch.setattr(bot, "get_user", lambda telegram_id: {"role": "passenger"})


def base_search_context(fake_context, search_time="18:00"):
    fake_context.user_data["search_from"] = "תל אביב"
    fake_context.user_data["search_to"] = "אוניברסיטת בר אילן"
    fake_context.user_data["search_from_coords"] = list(COORDS_TA)
    fake_context.user_data["search_to_coords"] = list(COORDS_BI)
    fake_context.user_data["search_time"] = search_time
    return fake_context


class TestDistanceMatchingIntegration:
    """Verifies open_search_flex includes/excludes rides based on MAX_PICKUP_DISTANCE_KM."""

    async def test_ride_within_distance_is_included(self, passenger_user, fake_context, monkeypatch):
        nearby_ride = make_ride("ride_near", COORDS_TA, COORDS_BI, "18:00")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [nearby_ride])

        base_search_context(fake_context)
        update = make_callback_update(bot.CB_FLEX_ANY)  # ignore time, isolate distance filter

        await bot.open_search_flex(update, fake_context)

        browse_rides = fake_context.chat_data["browse_rides"]
        assert [r["_id"] for r in browse_rides] == ["ride_near"]

    async def test_ride_beyond_distance_is_excluded(self, passenger_user, fake_context, monkeypatch):
        far_ride = make_ride("ride_far", COORDS_ME, COORDS_BI, "18:00")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [far_ride])

        base_search_context(fake_context)
        update = make_callback_update(bot.CB_FLEX_ANY)

        result = await bot.open_search_flex(update, fake_context)

        assert result == ConversationHandler.END
        assert "browse_rides" not in fake_context.chat_data
        update.callback_query.message.reply_text.assert_called()
        sent_text = update.callback_query.message.reply_text.call_args_list[-1].args[0]
        assert "לא מצאתי" in sent_text

    async def test_mixed_near_and_far_rides_only_near_one_kept(self, passenger_user, fake_context, monkeypatch):
        near = make_ride("ride_near", COORDS_TA, COORDS_BI, "18:00")
        far = make_ride("ride_far", COORDS_ME, COORDS_BI, "18:00")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [near, far])

        base_search_context(fake_context)
        update = make_callback_update(bot.CB_FLEX_ANY)

        await bot.open_search_flex(update, fake_context)

        browse_rides = fake_context.chat_data["browse_rides"]
        assert [r["_id"] for r in browse_rides] == ["ride_near"]


class TestFlexTimeWindowIntegration:
    """Verifies open_search_flex includes/excludes rides based on the FLEX time window."""

    async def test_ride_within_flex_window_is_included(self, passenger_user, fake_context, monkeypatch):
        # search is 18:00, ride is 18:10 -> diff of 10 minutes, within +-15
        ride = make_ride("ride_within", COORDS_TA, COORDS_BI, "18:10")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [ride])

        base_search_context(fake_context, search_time="18:00")
        update = make_callback_update(bot.CB_FLEX_15)

        await bot.open_search_flex(update, fake_context)

        browse_rides = fake_context.chat_data["browse_rides"]
        assert [r["_id"] for r in browse_rides] == ["ride_within"]

    async def test_ride_outside_flex_window_is_excluded(self, passenger_user, fake_context, monkeypatch):
        # search is 18:00, ride is 18:40 -> diff of 40 minutes, outside +-15
        ride = make_ride("ride_outside", COORDS_TA, COORDS_BI, "18:40")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [ride])

        base_search_context(fake_context, search_time="18:00")
        update = make_callback_update(bot.CB_FLEX_15)

        result = await bot.open_search_flex(update, fake_context)

        assert result == ConversationHandler.END
        assert "browse_rides" not in fake_context.chat_data

    async def test_flex_boundary_is_inclusive(self, passenger_user, fake_context, monkeypatch):
        # diff of exactly 15 minutes should still match (<=, not <)
        ride = make_ride("ride_boundary", COORDS_TA, COORDS_BI, "18:15")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [ride])

        base_search_context(fake_context, search_time="18:00")
        update = make_callback_update(bot.CB_FLEX_15)

        await bot.open_search_flex(update, fake_context)

        browse_rides = fake_context.chat_data["browse_rides"]
        assert [r["_id"] for r in browse_rides] == ["ride_boundary"]

    async def test_very_flexible_ignores_time_window(self, passenger_user, fake_context, monkeypatch):
        # CB_FLEX_ANY ("I'm very flexible") should keep a ride even far outside +-30
        ride = make_ride("ride_any_time", COORDS_TA, COORDS_BI, "23:59")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [ride])

        base_search_context(fake_context, search_time="06:00")
        update = make_callback_update(bot.CB_FLEX_ANY)

        await bot.open_search_flex(update, fake_context)

        browse_rides = fake_context.chat_data["browse_rides"]
        assert [r["_id"] for r in browse_rides] == ["ride_any_time"]


class TestNoMatchScenario:
    """Verifies the combined case: no ride satisfies both distance and time window."""

    async def test_no_rides_at_all_shows_no_match_message(self, passenger_user, fake_context, monkeypatch):
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [])

        base_search_context(fake_context)
        update = make_callback_update(bot.CB_FLEX_15)

        result = await bot.open_search_flex(update, fake_context)

        assert result == ConversationHandler.END
        sent_text = update.callback_query.message.reply_text.call_args_list[-1].args[0]
        assert "לא מצאתי" in sent_text

    async def test_ride_fails_both_distance_and_time_is_excluded(self, passenger_user, fake_context, monkeypatch):
        # far away AND outside the flex window - should not appear no matter which filter runs first
        ride = make_ride("ride_far_and_late", COORDS_ME, COORDS_BI, "23:00")
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [ride])

        base_search_context(fake_context, search_time="08:00")
        update = make_callback_update(bot.CB_FLEX_15)

        result = await bot.open_search_flex(update, fake_context)

        assert result == ConversationHandler.END
        assert "browse_rides" not in fake_context.chat_data
