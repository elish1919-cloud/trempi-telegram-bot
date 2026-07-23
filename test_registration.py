"""
Tests for the registration conversation flow (registration_conv):
register_or_update_user(), start(), reg_age(), reg_gender_button(),
reg_address(), reg_phone() (including phone validation edge cases), and
reg_role_button().

This flow was previously completely untested - see the coverage report from
earlier in the project (bot.py was at 36% overall, with the entire
registration path at 0%).
"""
import pytest
from telegram.ext import ConversationHandler

import bot
from conftest import make_callback_update, make_message_update


class TestRegisterOrUpdateUser:
    def test_new_user_is_created_with_default_fields(self, isolated_users_file):
        update = make_message_update("/start", user_id=555, first_name="Dana")

        user = bot.register_or_update_user(update)

        assert user["telegram_id"] == 555
        assert user["first_name"] == "Dana"
        assert user["is_registered"] is False
        assert user["age"] is None
        assert user["role"] is None
        assert bot.get_user(555) == user

    def test_existing_user_is_updated_not_duplicated(self, isolated_users_file):
        bot._save_json_list(
            bot.USERS_FILE,
            [{"telegram_id": 555, "first_name": "Old Name", "username": None,
              "age": 30, "gender": "female", "address": "Ashkelon", "phone": "0501234567",
              "default_role": "passenger", "role": "passenger",
              "is_registered": True, "registered_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}],
        )
        update = make_message_update("/start", user_id=555, first_name="New Name")

        user = bot.register_or_update_user(update)

        all_users = bot._load_json_list(bot.USERS_FILE)
        assert len(all_users) == 1  # not duplicated
        assert user["first_name"] == "New Name"  # refreshed from Telegram
        assert user["is_registered"] is True  # existing registration data preserved
        assert user["age"] == 30

    def test_old_user_record_missing_new_fields_gets_backfilled(self, isolated_users_file):
        # simulates a user record saved before the age/gender/address/phone fields existed
        bot._save_json_list(
            bot.USERS_FILE,
            [{"telegram_id": 555, "first_name": "Dana", "role": "driver"}],
        )
        update = make_message_update("/start", user_id=555, first_name="Dana")

        user = bot.register_or_update_user(update)

        assert user["age"] is None
        assert user["default_role"] == "driver"  # backfilled from the old "role" field
        assert user["is_registered"] is False


class TestStart:
    async def test_unregistered_user_is_prompted_to_register(self, isolated_users_file, fake_context):
        update = make_message_update("/start", user_id=555)

        await bot.start(update, fake_context)

        reply = update.message.reply_text.call_args.args[0]
        assert "הרשמה" in reply  # "registration"
        assert bot.get_user(555)["is_registered"] is False

    async def test_registered_user_sees_main_menu_without_crashing(self, isolated_users_file, fake_context):
        bot._save_json_list(
            bot.USERS_FILE,
            [{"telegram_id": 555, "first_name": "Dana", "role": "driver", "is_registered": True}],
        )
        update = make_message_update("/start", user_id=555, first_name="Dana")

        await bot.start(update, fake_context)

        update.message.reply_text.assert_awaited_once()


class TestRegAge:
    async def test_valid_age_is_accepted(self, fake_context):
        update = make_message_update("25")

        result = await bot.reg_age(update, fake_context)

        assert result == bot.REG_GENDER
        assert fake_context.user_data["reg_data"]["age"] == 25

    @pytest.mark.parametrize("bad_age", ["abc", "15", "121", "", "-5"])
    async def test_invalid_age_is_rejected_with_reprompt(self, fake_context, bad_age):
        update = make_message_update(bad_age)

        result = await bot.reg_age(update, fake_context)

        assert result == bot.REG_AGE
        assert "reg_data" not in fake_context.user_data
        update.message.reply_text.assert_awaited_once()

    @pytest.mark.parametrize("boundary_age", ["16", "120"])
    async def test_boundary_ages_are_accepted(self, fake_context, boundary_age):
        update = make_message_update(boundary_age)

        result = await bot.reg_age(update, fake_context)

        assert result == bot.REG_GENDER
        assert fake_context.user_data["reg_data"]["age"] == int(boundary_age)


class TestRegGenderButton:
    @pytest.mark.parametrize("data,expected", [
        (bot.CB_GENDER_MALE, "male"),
        (bot.CB_GENDER_FEMALE, "female"),
        (bot.CB_GENDER_OTHER, "other"),
    ])
    async def test_each_gender_choice_is_stored(self, fake_context, data, expected):
        update = make_callback_update(data)

        result = await bot.reg_gender_button(update, fake_context)

        assert result == bot.REG_ADDRESS
        assert fake_context.user_data["reg_data"]["gender"] == expected

    async def test_gender_data_survives_when_reg_data_not_pre_seeded(self, fake_context):
        assert "reg_data" not in fake_context.user_data
        update = make_callback_update(bot.CB_GENDER_MALE)

        await bot.reg_gender_button(update, fake_context)

        assert fake_context.user_data["reg_data"]["gender"] == "male"


class TestRegAddress:
    async def test_valid_address_is_accepted(self, fake_context):
        update = make_message_update("Tel Aviv")

        result = await bot.reg_address(update, fake_context)

        assert result == bot.REG_PHONE
        assert fake_context.user_data["reg_data"]["address"] == "Tel Aviv"

    async def test_empty_address_is_rejected_with_reprompt(self, fake_context):
        update = make_message_update("   ")

        result = await bot.reg_address(update, fake_context)

        assert result == bot.REG_ADDRESS
        assert "reg_data" not in fake_context.user_data or "address" not in fake_context.user_data.get("reg_data", {})


class TestRegPhone:
    @pytest.mark.parametrize("raw,normalized", [
        ("0501234567", "0501234567"),
        ("050-123-4567", "0501234567"),
        ("050 123 4567", "0501234567"),
        ("123456789", "123456789"),  # 9 digits, minimum valid length
    ])
    async def test_valid_phone_is_normalized_and_accepted(self, fake_context, raw, normalized):
        update = make_message_update(raw)

        result = await bot.reg_phone(update, fake_context)

        assert result == bot.REG_ROLE
        assert fake_context.user_data["reg_data"]["phone"] == normalized

    @pytest.mark.parametrize("bad_phone", [
        "12345678",       # 8 digits, one short of the minimum
        "12345678901",    # 11 digits, one over the maximum
        "abcdefghij",      # no digits at all
        "",
    ])
    async def test_invalid_phone_is_rejected_with_reprompt(self, fake_context, bad_phone):
        update = make_message_update(bad_phone)

        result = await bot.reg_phone(update, fake_context)

        assert result == bot.REG_PHONE
        assert "reg_data" not in fake_context.user_data or "phone" not in fake_context.user_data.get("reg_data", {})


class TestRegRoleButton:
    @pytest.mark.parametrize("data,expected_role,expected_stored_role", [
        (bot.CB_ROLE_DRIVER, "driver", "driver"),
        (bot.CB_ROLE_PASSENGER, "passenger", "passenger"),
        (bot.CB_ROLE_BOTH, "both", "driver"),  # "both" collapses to "driver" as the active role
    ])
    async def test_completes_registration_for_each_role_choice(
        self, isolated_users_file, fake_context, data, expected_role, expected_stored_role
    ):
        bot._save_json_list(bot.USERS_FILE, [{"telegram_id": 111, "first_name": "נועה", "is_registered": False}])
        fake_context.user_data["reg_data"] = {"age": 25, "gender": "female", "address": "Tel Aviv", "phone": "0501234567"}
        update = make_callback_update(data, user_id=111)

        result = await bot.reg_role_button(update, fake_context)

        assert result == ConversationHandler.END
        saved = bot.get_user(111)
        assert saved["default_role"] == expected_role
        assert saved["role"] == expected_stored_role
        assert saved["is_registered"] is True
        assert "reg_data" not in fake_context.user_data

    async def test_save_failure_shows_error_and_ends_conversation(self, isolated_users_file, fake_context):
        # user_id 999 was never seeded into users.json, so update_user_fields() finds nothing to update
        fake_context.user_data["reg_data"] = {"age": 25, "gender": "female", "address": "Tel Aviv", "phone": "0501234567"}
        update = make_callback_update(bot.CB_ROLE_DRIVER, user_id=999)

        result = await bot.reg_role_button(update, fake_context)

        assert result == ConversationHandler.END
        reply = update.callback_query.message.reply_text.call_args.args[0]
        assert "בעיה" in reply  # "problem"
