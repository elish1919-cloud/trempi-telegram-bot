"""
Edge-case / graceful-degradation tests.

The lecturer's requirement is that the bot never crashes/hangs on bad input or a
flaky external dependency - it should always reply with something sensible instead
of silently dying (which, in a real Telegram bot, means the user just gets no
response at all).

Covers five scenarios:
1. An unrecognized/invalid city name (geocoding finds nothing -> returns None).
2. An invalid time format typed by the user during search.
3. No rides match the search (distance/time window) - already covered in detail by
   test_matching.py::TestNoMatchScenario; the two smoke tests below just confirm the
   same "no match" behavior is reachable from this file's scenario-based framing too.
4. A genuine external-service failure: geocode_place() or a MongoDB call raising an
   exception instead of failing quietly.
5. Invalid time input during ride creation (ask_when()) - previously accepted any
   text with zero validation; now restricted to the exact formats its own prompt
   promises (HH:MM, "עכשיו", "מחר בבוקר"), reprompting on anything else.

Bugs found and fixed while writing these tests (see also README "Edge Case Handling"):
- ask_when() (ride creation) had no error handling around geocode_place()/add_ride() -
  if MongoDB (or geocoding) raised instead of just returning None/being slow, the
  exception propagated out of the handler and the user creating a ride got no reply
  at all. Now wrapped in try/except with a friendly Hebrew error message.
- open_search_flex() (ride search/matching) had the same gap around
  get_open_rides_by_role_from_mongo() and the distance/time filtering - now wrapped
  the same way.
- open_search_to() (search destination step) had no protection around geocode_place();
  a raised exception there would crash mid-search. Now caught and treated the same as
  "place not found" (coords=None), which the rest of the search flow already handles.
"""
import pytest
from telegram.ext import ConversationHandler

import bot
from conftest import make_callback_update, make_message_update


@pytest.fixture
def driver_user(monkeypatch):
    monkeypatch.setattr(bot, "get_user", lambda telegram_id: {"role": "driver"})


@pytest.fixture
def passenger_user(monkeypatch):
    monkeypatch.setattr(bot, "get_user", lambda telegram_id: {"role": "passenger"})


class TestUnrecognizedCityName:
    """geocode_place() returns None for a city Nominatim can't find - this must not
    block ride creation or search, just leave the coordinates empty."""

    async def test_ride_creation_succeeds_with_unrecognized_city(
        self, driver_user, fake_context, monkeypatch
    ):
        # simulates geocode_place() finding nothing for a nonsense place name
        monkeypatch.setattr(bot, "geocode_place", _async_return(None))
        monkeypatch.setattr(bot, "add_ride", lambda ride: {**ride, "ride_id": "abc123"})

        fake_context.user_data["ride_from"] = "asdkfjhaskdjfh - not a real place"
        fake_context.user_data["ride_to"] = "Bar-Ilan University"

        update = make_message_update("18:30")
        result = await bot.ask_when(update, fake_context)

        assert result == ConversationHandler.END
        # the success message was still sent - no crash, no error message
        first_reply = update.message.reply_text.call_args_list[0].args[0]
        assert "קיבלתי" in first_reply

    async def test_search_destination_with_unrecognized_city_does_not_crash(
        self, fake_context, monkeypatch
    ):
        monkeypatch.setattr(bot, "geocode_place", _async_return(None))

        update = make_message_update("asdkfjhaskdjfh - not a real place")
        result = await bot.open_search_to(update, fake_context)

        assert result == bot.SEARCH_TIME
        assert fake_context.user_data["search_to_coords"] is None
        update.message.reply_text.assert_awaited_once()


class TestRideCreationTimeValidation:
    """ask_when() now validates the ride's 'when' field against the exact formats
    its own prompt promises (HH:MM / 'עכשיו' / 'מחר בבוקר') instead of accepting
    any text verbatim, reprompting in the same ASK_WHEN state on anything else."""

    async def test_valid_hhmm_is_accepted(self, driver_user, fake_context, monkeypatch):
        monkeypatch.setattr(bot, "geocode_place", _async_return((32.0853, 34.7818)))
        monkeypatch.setattr(bot, "add_ride", lambda ride: {**ride, "ride_id": "abc123"})
        fake_context.user_data["ride_from"] = "Tel Aviv"
        fake_context.user_data["ride_to"] = "Bar-Ilan University"

        update = make_message_update("18:30")
        result = await bot.ask_when(update, fake_context)

        assert result == ConversationHandler.END
        first_reply = update.message.reply_text.call_args_list[0].args[0]
        assert "קיבלתי" in first_reply

    async def test_now_phrase_is_accepted(self, driver_user, fake_context, monkeypatch):
        monkeypatch.setattr(bot, "geocode_place", _async_return((32.0853, 34.7818)))
        monkeypatch.setattr(bot, "add_ride", lambda ride: {**ride, "ride_id": "abc123"})
        fake_context.user_data["ride_from"] = "Tel Aviv"
        fake_context.user_data["ride_to"] = "Bar-Ilan University"

        update = make_message_update("עכשיו")
        result = await bot.ask_when(update, fake_context)

        assert result == ConversationHandler.END
        first_reply = update.message.reply_text.call_args_list[0].args[0]
        assert "קיבלתי" in first_reply

    async def test_tomorrow_morning_phrase_is_accepted(self, driver_user, fake_context, monkeypatch):
        monkeypatch.setattr(bot, "geocode_place", _async_return((32.0853, 34.7818)))
        monkeypatch.setattr(bot, "add_ride", lambda ride: {**ride, "ride_id": "abc123"})
        fake_context.user_data["ride_from"] = "Tel Aviv"
        fake_context.user_data["ride_to"] = "Bar-Ilan University"

        update = make_message_update("מחר בבוקר")
        result = await bot.ask_when(update, fake_context)

        assert result == ConversationHandler.END
        first_reply = update.message.reply_text.call_args_list[0].args[0]
        assert "קיבלתי" in first_reply

    async def test_gibberish_is_rejected_with_reprompt(self, fake_context):
        update = make_message_update("בכבכב")

        result = await bot.ask_when(update, fake_context)

        assert result == bot.ASK_WHEN  # stays in the same state, asks again
        reply = update.message.reply_text.call_args.args[0]
        assert "עכשיו" in reply and "18:30" in reply
        update.message.reply_text.assert_awaited_once()

    async def test_empty_input_is_rejected_with_reprompt(self, fake_context):
        update = make_message_update("   ")

        result = await bot.ask_when(update, fake_context)

        assert result == bot.ASK_WHEN
        update.message.reply_text.assert_awaited_once()


class TestInvalidTimeFormat:
    """The search flow validates HH:MM strictly and must reprompt, not crash,
    on gibberish input."""

    async def test_gibberish_time_reprompts_instead_of_crashing(self, fake_context):
        update = make_message_update("askdjhaskjdh")

        result = await bot.open_search_time(update, fake_context)

        assert result == bot.SEARCH_TIME  # stays in the same state, asks again
        assert "search_time" not in fake_context.user_data
        reply = update.message.reply_text.call_args.args[0]
        assert "פורמט" in reply  # asks for the right format, no traceback/crash

    async def test_partial_time_like_missing_minutes_reprompts(self, fake_context):
        update = make_message_update("18")

        result = await bot.open_search_time(update, fake_context)

        assert result == bot.SEARCH_TIME
        update.message.reply_text.assert_awaited_once()

    async def test_valid_time_is_accepted_for_contrast(self, fake_context):
        # sanity check that the reprompt above is really about invalid input,
        # not the handler always looping
        update = make_message_update("18:30")

        result = await bot.open_search_time(update, fake_context)

        assert result == bot.SEARCH_FLEX
        assert fake_context.user_data["search_time"] == "18:30"


class TestNoMatchingRidesExplicit:
    """Smoke tests confirming 'no rides match' is a normal, non-crashing outcome.
    Full distance/FLEX combinations are covered in test_matching.py::TestNoMatchScenario."""

    async def test_no_open_rides_at_all_shows_friendly_message(
        self, passenger_user, fake_context, monkeypatch
    ):
        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", lambda role: [])
        fake_context.user_data["search_from_coords"] = [32.0853, 34.7818]
        fake_context.user_data["search_to_coords"] = [32.0693, 34.8433]
        fake_context.user_data["search_time"] = "18:00"

        update = make_callback_update(bot.CB_FLEX_15)
        result = await bot.open_search_flex(update, fake_context)

        assert result == ConversationHandler.END
        reply = update.callback_query.message.reply_text.call_args_list[-1].args[0]
        assert "לא מצאתי" in reply
        assert "browse_rides" not in fake_context.chat_data


class TestExternalServiceFailure:
    """Simulates MongoDB / geocoding raising a real exception (not just returning
    None/empty) - the bot must reply with a friendly message and end the
    conversation cleanly instead of leaving the user hanging."""

    async def test_ride_creation_survives_database_failure(
        self, driver_user, fake_context, monkeypatch
    ):
        monkeypatch.setattr(bot, "geocode_place", _async_return((32.0853, 34.7818)))

        def raise_db_error(ride):
            raise ConnectionError("simulated MongoDB outage")

        monkeypatch.setattr(bot, "add_ride", raise_db_error)

        fake_context.user_data["ride_from"] = "Tel Aviv"
        fake_context.user_data["ride_to"] = "Bar-Ilan University"

        update = make_message_update("18:30")
        result = await bot.ask_when(update, fake_context)

        assert result == ConversationHandler.END
        reply = update.message.reply_text.call_args.args[0]
        assert "תקלה" in reply

    async def test_ride_creation_survives_geocoding_failure(
        self, driver_user, fake_context, monkeypatch
    ):
        async def raise_geocode_error(place):
            raise TimeoutError("simulated Nominatim timeout")

        monkeypatch.setattr(bot, "geocode_place", raise_geocode_error)

        fake_context.user_data["ride_from"] = "Tel Aviv"
        fake_context.user_data["ride_to"] = "Bar-Ilan University"

        update = make_message_update("18:30")
        result = await bot.ask_when(update, fake_context)

        assert result == ConversationHandler.END
        reply = update.message.reply_text.call_args.args[0]
        assert "תקלה" in reply

    async def test_search_survives_database_failure(
        self, passenger_user, fake_context, monkeypatch
    ):
        def raise_db_error(role):
            raise ConnectionError("simulated MongoDB outage")

        monkeypatch.setattr(bot, "get_open_rides_by_role_from_mongo", raise_db_error)
        fake_context.user_data["search_from_coords"] = [32.0853, 34.7818]
        fake_context.user_data["search_to_coords"] = [32.0693, 34.8433]
        fake_context.user_data["search_time"] = "18:00"

        update = make_callback_update(bot.CB_FLEX_15)
        result = await bot.open_search_flex(update, fake_context)

        assert result == ConversationHandler.END
        reply = update.callback_query.message.reply_text.call_args_list[-1].args[0]
        assert "תקלה" in reply

    async def test_search_destination_survives_geocoding_failure(self, fake_context, monkeypatch):
        async def raise_geocode_error(place):
            raise TimeoutError("simulated Nominatim timeout")

        monkeypatch.setattr(bot, "geocode_place", raise_geocode_error)

        update = make_message_update("Tel Aviv")
        result = await bot.open_search_to(update, fake_context)

        assert result == bot.SEARCH_TIME
        assert fake_context.user_data["search_to_coords"] is None
        update.message.reply_text.assert_awaited_once()


def _async_return(value):
    async def _coro(*args, **kwargs):
        return value
    return _coro
