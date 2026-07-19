"""
Date/time validation tests.

Covers the parsing/validation helpers used while a user searches for a ride:
- _extract_hhmm: pulls an HH:MM time out of free text (used in open_search_time)
- _hhmm_to_minutes: converts "HH:MM" to minutes-since-midnight (used for FLEX matching)
- _is_valid_ddmm: validates a DD/MM date (used in open_search_date)

Note: ask_when() (ride creation "when" field) intentionally accepts ANY free text
("עכשיו" / "18:30" / "מחר בבוקר") with no format validation - that's by design,
so it is not covered here. The strict HH:MM validation only applies to search time.
"""
import bot


class TestExtractHHMM:
    def test_valid_hhmm_returned_as_is(self):
        assert bot._extract_hhmm("18:30") == "18:30"

    def test_single_digit_hour_is_accepted(self):
        assert bot._extract_hhmm("9:05") == "9:05"

    def test_midnight_is_valid(self):
        assert bot._extract_hhmm("00:00") == "00:00"

    def test_free_text_like_tomorrow_morning_has_no_time(self):
        # "מחר בבוקר" (tomorrow morning) has no HH:MM in it at all
        assert bot._extract_hhmm("מחר בבוקר") is None

    def test_word_now_has_no_time(self):
        assert bot._extract_hhmm("עכשיו") is None

    def test_hour_out_of_range_rejected(self):
        assert bot._extract_hhmm("25:00") is None

    def test_minute_out_of_range_rejected(self):
        assert bot._extract_hhmm("12:60") is None

    def test_single_digit_minute_rejected(self):
        assert bot._extract_hhmm("8:5") is None

    def test_time_embedded_in_sentence_with_space_is_found(self):
        assert bot._extract_hhmm("אני מגיע ב- 18:30 בערך") == "18:30"

    def test_empty_and_none_input(self):
        assert bot._extract_hhmm("") is None
        assert bot._extract_hhmm(None) is None


class TestHHMMToMinutes:
    def test_converts_evening_time(self):
        assert bot._hhmm_to_minutes("18:30") == 18 * 60 + 30

    def test_converts_midnight(self):
        assert bot._hhmm_to_minutes("00:00") == 0

    def test_invalid_format_returns_none(self):
        assert bot._hhmm_to_minutes("not-a-time") is None

    def test_none_input_returns_none(self):
        assert bot._hhmm_to_minutes(None) is None


class TestIsValidDDMM:
    def test_valid_dates(self):
        assert bot._is_valid_ddmm("18/01") is True
        assert bot._is_valid_ddmm("31/12") is True
        assert bot._is_valid_ddmm("01/01") is True

    def test_day_zero_is_invalid(self):
        assert bot._is_valid_ddmm("00/01") is False

    def test_day_above_31_is_invalid(self):
        assert bot._is_valid_ddmm("32/01") is False

    def test_month_above_12_is_invalid(self):
        assert bot._is_valid_ddmm("18/13") is False

    def test_missing_leading_zero_is_invalid(self):
        # the bot always prompts for DD/MM with leading zeros, e.g. "18/01"
        assert bot._is_valid_ddmm("1/1") is False

    def test_empty_and_none_input(self):
        assert bot._is_valid_ddmm("") is False
        assert bot._is_valid_ddmm(None) is False
