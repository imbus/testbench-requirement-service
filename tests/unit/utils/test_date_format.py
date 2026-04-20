import logging
from datetime import datetime, timedelta, timezone

import pytest

from testbench_requirement_service.utils.date_format import (
    _convert_java_letter_token,
    _is_python_strftime_format,
    _normalize_to_utc,
    java_to_python_date_format,
    parse_date_string,
)


class TestJavaToPythonDateFormat:
    @pytest.mark.parametrize(
        ("java_fmt", "expected"),
        [
            ("yyyy-MM-dd", "%Y-%m-%d"),
            ("yyyy-MM-dd HH:mm:ss", "%Y-%m-%d %H:%M:%S"),
            ("dd.MM.yyyy", "%d.%m.%Y"),
            ("dd/MM/yy hh:mm:ss a", "%d/%m/%y %I:%M:%S %p"),
            ("EEE, dd MMM yyyy", "%a, %d %b %Y"),
            ("EEEE, dd MMMM yyyy", "%A, %d %B %Y"),
            ("yyyy-MM-dd'T'HH:mm:ss", "%Y-%m-%dT%H:%M:%S"),
            ("yyyy-MM-dd'T'HH:mm:ss.SSSXXX", "%Y-%m-%dT%H:%M:%S.%f%z"),
        ],
    )
    def test_common_patterns(self, java_fmt: str, expected: str) -> None:
        assert java_to_python_date_format(java_fmt) == expected

    @pytest.mark.parametrize(
        ("java_fmt", "expected"),
        [
            ("y", "%Y"),
            ("yy", "%y"),
            ("yyy", "%Y"),
            ("yyyy", "%Y"),
        ],
    )
    def test_year_variants(self, java_fmt: str, expected: str) -> None:
        assert java_to_python_date_format(java_fmt) == expected

    @pytest.mark.parametrize(
        ("java_fmt", "expected"),
        [
            ("M", "%m"),
            ("MM", "%m"),
            ("MMM", "%b"),
            ("MMMM", "%B"),
        ],
    )
    def test_month_variants(self, java_fmt: str, expected: str) -> None:
        assert java_to_python_date_format(java_fmt) == expected

    @pytest.mark.parametrize(
        ("java_fmt", "expected"),
        [
            ("E", "%a"),
            ("EE", "%a"),
            ("EEE", "%a"),
            ("EEEE", "%A"),
        ],
    )
    def test_day_name_variants(self, java_fmt: str, expected: str) -> None:
        assert java_to_python_date_format(java_fmt) == expected

    @pytest.mark.parametrize(
        ("java_fmt", "expected"),
        [
            ("H", "%H"),  # 0-23
            ("HH", "%H"),
            ("h", "%I"),  # 1-12
            ("hh", "%I"),
            ("k", "%H"),  # 1-24 (approx)
            ("kk", "%H"),
            ("K", "%I"),  # 0-11 (approx)
            ("KK", "%I"),
        ],
    )
    def test_hour_variants(self, java_fmt: str, expected: str) -> None:
        assert java_to_python_date_format(java_fmt) == expected

    @pytest.mark.parametrize("java_fmt", ["S", "SS", "SSS"])
    def test_fractional_seconds_map_to_microseconds(self, java_fmt: str) -> None:
        assert java_to_python_date_format(java_fmt) == "%f"

    @pytest.mark.parametrize(
        ("java_fmt", "expected"),
        [
            ("Z", "%z"),
            ("ZZ", "%z"),
            ("ZZZ", "%z"),
            ("X", "%z"),
            ("XX", "%z"),
            ("XXX", "%z"),
            ("z", "%Z"),
            ("zzzz", "%Z"),
        ],
    )
    def test_timezone_variants(self, java_fmt: str, expected: str) -> None:
        assert java_to_python_date_format(java_fmt) == expected

    def test_quoted_literal_T(self) -> None:  # noqa: N802
        result = java_to_python_date_format("yyyy-MM-dd'T'HH:mm:ss")
        assert result == "%Y-%m-%dT%H:%M:%S"

    def test_quoted_literal_word(self) -> None:
        result = java_to_python_date_format("dd.MM.yyyy 'at' HH:mm")
        assert result == "%d.%m.%Y at %H:%M"

    def test_standalone_double_quote_becomes_single_quote(self) -> None:
        # '' outside any quoted block → literal single-quote
        result = java_to_python_date_format("dd''MM")
        assert result == "%d'%m"

    def test_escaped_quote_inside_quoted_block(self) -> None:
        # '' inside a quoted block → literal single-quote
        result = java_to_python_date_format("dd'o''clock'MM")
        assert result == "%do'clock%m"

    def test_unclosed_quoted_block_consumed_to_end(self) -> None:
        # Malformed input: opening quote never closed — tokenizer consumes until EOF.
        result = java_to_python_date_format("yyyy'rest")
        assert result == "%Yrest"

    def test_literal_percent_is_escaped_to_double_percent(self) -> None:
        result = java_to_python_date_format("yyyy%MM")
        assert result == "%Y%%%m"

    def test_overlong_month_MMMMM_falls_back_to_full_name(self) -> None:  # noqa: N802
        # 5 M's → same semantics as MMMM in Java
        assert java_to_python_date_format("MMMMM") == "%B"

    def test_overlong_year_yyyyy_falls_back_to_4digit(self) -> None:
        assert java_to_python_date_format("yyyyy") == "%Y"

    def test_overlong_day_name_EEEEE_falls_back_to_full_name(self) -> None:  # noqa: N802
        assert java_to_python_date_format("EEEEE") == "%A"

    def test_unknown_pattern_letter_passes_through(self) -> None:
        # 'V' is not a standard Java date letter
        result = java_to_python_date_format("yyyy-VV")
        assert result == "%Y-VV"

    def test_non_alpha_non_percent_chars_pass_through(self) -> None:
        result = java_to_python_date_format("yyyy/MM/dd")
        assert result == "%Y/%m/%d"


class TestConvertJavaLetterToken:
    def test_exact_match_returned(self) -> None:
        assert _convert_java_letter_token("yyyy") == "%Y"

    def test_unknown_letter_passes_through(self) -> None:
        assert _convert_java_letter_token("VV") == "VV"

    def test_overlong_month_falls_back_to_longest_known(self) -> None:
        # "MMMMM" (5) → tries "MMMM" (4) → "%B"
        assert _convert_java_letter_token("MMMMM") == "%B"

    def test_overlong_year_falls_back(self) -> None:
        # "yyyyy" (5) → tries "yyyy" (4) → "%Y"
        assert _convert_java_letter_token("yyyyy") == "%Y"

    def test_single_known_token(self) -> None:
        assert _convert_java_letter_token("MM") == "%m"


class TestIsPythonStrftimeFormat:
    @pytest.mark.parametrize(
        "fmt",
        ["%Y-%m-%d", "%d.%m.%Y %H:%M:%S", "%Y", "%I:%M %p", "%Y-%m-%dT%H:%M:%S"],
    )
    def test_python_format_detected_as_true(self, fmt: str) -> None:
        assert _is_python_strftime_format(fmt) is True

    @pytest.mark.parametrize(
        "fmt",
        ["yyyy-MM-dd", "dd.MM.yyyy HH:mm:ss", "M/d/yy", "EEE dd MMM yyyy"],
    )
    def test_java_format_detected_as_false(self, fmt: str) -> None:
        assert _is_python_strftime_format(fmt) is False


class TestNormalizeToUtc:
    def test_naive_datetime_gets_utc_tzinfo(self) -> None:
        naive = datetime(2024, 3, 15, 10, 30, 0)  # noqa: DTZ001
        result = _normalize_to_utc(naive)
        assert result.tzinfo == timezone.utc
        assert result == datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_utc_aware_datetime_returned_unchanged(self) -> None:
        utc = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _normalize_to_utc(utc)
        assert result == utc
        assert result.tzinfo == timezone.utc

    def test_positive_offset_converted_to_utc(self) -> None:
        # 12:00 +02:00 → 10:00 UTC (instant preserved, representation changed)
        plus2 = timezone(timedelta(hours=2))
        dt = datetime(2024, 3, 15, 12, 0, 0, tzinfo=plus2)
        result = _normalize_to_utc(dt)
        assert result == datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_negative_offset_converted_to_utc(self) -> None:
        # 08:00 -05:00 → 13:00 UTC
        minus5 = timezone(timedelta(hours=-5))
        dt = datetime(2024, 3, 15, 8, 0, 0, tzinfo=minus5)
        result = _normalize_to_utc(dt)
        assert result == datetime(2024, 3, 15, 13, 0, 0, tzinfo=timezone.utc)

    def test_instant_is_preserved_during_conversion(self) -> None:
        plus2 = timezone(timedelta(hours=2))
        dt = datetime(2024, 3, 15, 12, 0, 0, tzinfo=plus2)
        result = _normalize_to_utc(dt)
        # Both represent the same point in time
        assert result.utctimetuple() == dt.utctimetuple()


class TestParseDateString:
    # --- Java format, naive strings → UTC ---

    def test_java_format_datetime_naive(self) -> None:
        result = parse_date_string("2024-03-15 10:30:00", "yyyy-MM-dd HH:mm:ss")
        assert result == datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_java_format_date_only(self) -> None:
        result = parse_date_string("2024-03-15", "yyyy-MM-dd")
        assert result == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

    def test_java_format_with_dots(self) -> None:
        result = parse_date_string("15.03.2024", "dd.MM.yyyy")
        assert result == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

    def test_java_format_2digit_year(self) -> None:
        result = parse_date_string("15.03.24", "dd.MM.yy")
        assert result == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

    # --- Python format, naive strings → UTC ---

    def test_python_format_datetime_naive(self) -> None:
        result = parse_date_string("2024-03-15 10:30:00", "%Y-%m-%d %H:%M:%S")
        assert result == datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_python_format_date_only(self) -> None:
        result = parse_date_string("2024-03-15", "%Y-%m-%d")
        assert result == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

    # --- Offset-aware strings → UTC (key correctness check) ---

    def test_java_format_positive_offset_converted_to_utc(self) -> None:
        # 12:00 +0200 → 10:00 UTC  (NOT 12:00 UTC — that would be the old bug)
        result = parse_date_string("2024-03-15 12:00:00+0200", "yyyy-MM-dd HH:mm:ssZ")
        assert result == datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_python_format_negative_offset_converted_to_utc(self) -> None:
        # 08:00 -0500 → 13:00 UTC
        result = parse_date_string("2024-03-15 08:00:00-0500", "%Y-%m-%d %H:%M:%S%z")
        assert result == datetime(2024, 3, 15, 13, 0, 0, tzinfo=timezone.utc)

    def test_offset_aware_instant_is_preserved(self) -> None:
        # Both sides of the assertion represent the same moment.
        expected_utc = datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = parse_date_string("2024-03-15 12:00:00+0200", "yyyy-MM-dd HH:mm:ssZ")
        assert result == expected_utc

    # --- dateutil fallback ---

    def test_dateutil_fallback_emits_warning_log(self, caplog: pytest.LogCaptureFixture) -> None:  # type: ignore[name-defined]
        with caplog.at_level(logging.WARNING):
            result = parse_date_string("March 15, 2024", "yyyy-MM-dd")
        assert result == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert "dateutil" in caplog.text
        assert caplog.records[-1].levelname == "WARNING"

    def test_dateutil_fallback_result_is_utc_aware(self, caplog: pytest.LogCaptureFixture) -> None:  # type: ignore[name-defined]
        with caplog.at_level(logging.WARNING):
            result = parse_date_string("15th March 2024", "yyyy-MM-dd")
        assert result.tzinfo is not None
        assert result.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
        assert len(caplog.records) > 0

    # --- Error handling ---

    def test_unparseable_value_raises_value_error(self, caplog: pytest.LogCaptureFixture) -> None:  # type: ignore[name-defined]
        with (
            caplog.at_level(logging.WARNING),
            pytest.raises(ValueError, match="automatic detection"),
        ):
            parse_date_string("not-a-date-xyz!!!", "yyyy-MM-dd")
        assert len(caplog.records) > 0

    # --- Result is always UTC-aware ---

    @pytest.mark.parametrize(
        ("date_str", "fmt"),
        [
            ("2024-03-15 10:30:00", "yyyy-MM-dd HH:mm:ss"),
            ("2024-03-15 10:30:00", "%Y-%m-%d %H:%M:%S"),
            ("15.03.2024", "dd.MM.yyyy"),
            ("2024-03-15", "%Y-%m-%d"),
            ("2024-03-15 12:00:00+0200", "yyyy-MM-dd HH:mm:ssZ"),
        ],
    )
    def test_result_is_always_utc_aware(self, date_str: str, fmt: str) -> None:
        result = parse_date_string(date_str, fmt)
        assert result.tzinfo is not None
        assert result.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
