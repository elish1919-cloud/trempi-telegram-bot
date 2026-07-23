"""
Tests for ride browsing (_show_browse_ride(), my_cmd(), _browse_keyboard())
and the recommendation-surfacing handlers (open_search_start(),
handle_recommendation_yes(), handle_recommendation_no()).

Both areas were previously completely untested - see the coverage report
from earlier in the project.
"""
import database
import pytest
from telegram.ext import ConversationHandler

import bot
from conftest import make_callback_update, make_message_update


class TestBrowseKeyboard:
    def test_includes_join_and_next_buttons_when_another_ride_exists(self):
        markup = bot._browse_keyboard("ride1", "ride2")

        callback_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "join_ride1" in callback_data
        assert "next_ride2" in callback_data

    def test_shows_main_menu_button_when_no_next_ride(self):
        markup = bot._browse_keyboard("ride1", None)

        callback_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "join_ride1" in callback_data
        assert "main_menu" in callback_data
        assert not any(cb.startswith("next_") for cb in callback_data)


class TestShowBrowseRide:
    async def test_empty_ride_list_shows_no_more_rides_message(self, fake_context):
        update = make_message_update("dummy")
        # browse_rides intentionally left empty

        await bot._show_browse_ride(update, fake_context)

        update.message.reply_text.assert_awaited_once()
        reply = update.message.reply_text.call_args.args[0]
        assert "אין עוד טרמפים" in reply

    async def test_shows_current_ride_details(self, fake_context):
        fake_context.chat_data["browse_rides"] = [
            {"_id": "ride1", "from": "Tel Aviv", "to": "Bar-Ilan University", "when": "18:00"},
            {"_id": "ride2", "from": "Haifa", "to": "Bar-Ilan University", "when": "19:00"},
        ]
        fake_context.chat_data["browse_idx"] = 0
        update = make_message_update("dummy")

        await bot._show_browse_ride(update, fake_context)

        reply = update.message.reply_text.call_args.args[0]
        assert "Tel Aviv" in reply
        assert "Bar-Ilan University" in reply

    async def test_edit_mode_uses_edit_message_text_not_reply(self, fake_context):
        fake_context.chat_data["browse_rides"] = [
            {"_id": "ride1", "from": "Tel Aviv", "to": "Bar-Ilan University", "when": "18:00"},
        ]
        fake_context.chat_data["browse_idx"] = 0
        update = make_callback_update(bot.CB_NEXT)

        await bot._show_browse_ride(update, fake_context, edit=True)

        update.callback_query.edit_message_text.assert_awaited_once()

    async def test_index_past_end_of_list_shows_no_more_rides_message(self, fake_context):
        fake_context.chat_data["browse_rides"] = [{"_id": "ride1", "from": "A", "to": "B", "when": "18:00"}]
        fake_context.chat_data["browse_idx"] = 5  # out of range
        update = make_message_update("dummy")

        await bot._show_browse_ride(update, fake_context)

        reply = update.message.reply_text.call_args.args[0]
        assert "אין עוד טרמפים" in reply


class TestMyCmd:
    async def test_no_rides_shows_empty_state_message(self, fake_context, monkeypatch):
        monkeypatch.setattr(bot, "list_my_rides", lambda telegram_id: [])
        update = make_message_update("/my")

        await bot.my_cmd(update, fake_context)

        reply = update.message.reply_text.call_args.args[0]
        assert "אין לך עדיין בקשות" in reply

    async def test_lists_recent_rides(self, fake_context, monkeypatch):
        rides = [
            {"ride_id": 1, "role": "driver", "from": "Tel Aviv", "to": "Bar-Ilan University", "when": "18:00", "status": "open"},
            {"ride_id": 2, "role": "driver", "from": "Haifa", "to": "Jerusalem", "when": "19:00", "status": "picked"},
        ]
        monkeypatch.setattr(bot, "list_my_rides", lambda telegram_id: rides)
        update = make_message_update("/my")

        await bot.my_cmd(update, fake_context)

        reply = update.message.reply_text.call_args.args[0]
        assert "Tel Aviv" in reply
        assert "Haifa" in reply


@pytest.fixture
def registered_user(monkeypatch):
    monkeypatch.setattr(bot, "get_user", lambda telegram_id: {"role": "passenger"})


class TestOpenSearchStart:
    async def test_unregistered_user_is_blocked(self, fake_context, monkeypatch):
        monkeypatch.setattr(bot, "get_user", lambda telegram_id: None)
        update = make_message_update("/open")

        result = await bot.open_search_start(update, fake_context)

        assert result == ConversationHandler.END
        reply = update.message.reply_text.call_args.args[0]
        assert "/start" in reply

    async def test_new_user_with_no_history_skips_straight_to_day_question(
        self, registered_user, fake_context, monkeypatch
    ):
        monkeypatch.setattr(bot, "get_last_searched_destination", lambda telegram_id: None)
        update = make_message_update("/open")

        result = await bot.open_search_start(update, fake_context)

        assert result == bot.SEARCH_DAY
        update.message.reply_text.assert_awaited_once()

    async def test_returning_user_sees_recommendation_buttons(
        self, registered_user, fake_context, monkeypatch
    ):
        monkeypatch.setattr(bot, "get_last_searched_destination", lambda telegram_id: "Bar-Ilan University")
        monkeypatch.setattr(database, "get_most_popular_destination", lambda: "Jerusalem")
        update = make_message_update("/open")

        result = await bot.open_search_start(update, fake_context)

        assert result == bot.SEARCH_RECOMMENDATION
        assert fake_context.user_data["recommended_to"] == "Bar-Ilan University"
        markup = update.message.reply_text.call_args.kwargs["reply_markup"]
        callback_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "rec_yes" in callback_data
        assert "rec_no" in callback_data
        assert "home_destination" in callback_data


class TestHandleRecommendationYesNo:
    async def test_yes_carries_recommended_destination_into_search(self, fake_context):
        fake_context.user_data["recommended_to"] = "Bar-Ilan University"
        update = make_callback_update("rec_yes")

        result = await bot.handle_recommendation_yes(update, fake_context)

        assert result == bot.SEARCH_DAY
        assert fake_context.user_data["search_to"] == "Bar-Ilan University"

    async def test_no_clears_recommendation_and_continues(self, fake_context):
        fake_context.user_data["recommended_to"] = "Bar-Ilan University"
        update = make_callback_update("rec_no")

        result = await bot.handle_recommendation_no(update, fake_context)

        assert result == bot.SEARCH_DAY
        assert "recommended_to" not in fake_context.user_data
        assert "search_to" not in fake_context.user_data
