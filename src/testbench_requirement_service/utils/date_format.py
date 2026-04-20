import logging
import re
from datetime import datetime, timezone

from dateutil import parser as dateutil_parser
from dateutil.parser import ParserError

logger = logging.getLogger(__name__)

# Flat token map: Java pattern token string → Python strftime code.
# Tokens that vary by repeat count are listed as separate entries.
# All others use a single entry (repeat count only affects zero-padding in Java,
# which has no Python strftime equivalent).
#
# Known approximations:
#   S   → %f  : Java=milliseconds (3 digits), Python=microseconds (6 digits).
#               For strptime: zero-pad the value to 6 digits.
#               For strftime: truncate %f output to 3 digits.
#   k   → %H  : Java hour 1-24; hour 24 wraps to 00 in Python.
#   K   → %I  : Java hour 0-11; hour 0 maps to 12 in Python's %I.
#   Y   → %Y  : ISO week-year differs from calendar year near week 1/53 boundaries.
#   z   → %Z  : Timezone name via %Z is unreliable in strptime.
#   X   → %z  : Bare 'Z' (UTC) only supported in Python 3.7+.
#               X  (1 letter) = hours only in Java (e.g. "-08"), %z expects ±HHMM — lossy.
#               XX (2 letters) = "-0800" — best match for %z.
#               XXX (3 letters) = "-08:00" — colon form, Python 3.7+ only.
_JAVA_TOKEN_MAP: dict[str, str] = {
    # Year — yy = 2-digit, all others = 4-digit
    "yyyy": "%Y",
    "yyy": "%Y",
    "yy": "%y",
    "y": "%Y",
    "YYYY": "%Y",
    "YYY": "%Y",
    "YY": "%y",
    "Y": "%Y",
    # Month — 4+ = full name, 3 = abbrev, 1-2 = numeric
    "MMMM": "%B",
    "MMM": "%b",
    "MM": "%m",
    "M": "%m",
    "LLLL": "%B",
    "LLL": "%b",
    "LL": "%m",
    "L": "%m",
    # Day name — 4+ = full, 1-3 = abbreviated
    "EEEE": "%A",
    "EEE": "%a",
    "EE": "%a",
    "E": "%a",
    # Day of month
    "dd": "%d",
    "d": "%d",
    # Hours
    "HH": "%H",
    "H": "%H",  # 0-23
    "hh": "%I",
    "h": "%I",  # 1-12
    "kk": "%H",
    "k": "%H",  # 1-24 (approx)
    "KK": "%I",
    "K": "%I",  # 0-11 (approx)
    # Minutes / Seconds / Fractional seconds
    "mm": "%M",
    "m": "%M",
    "ss": "%S",
    "s": "%S",
    "SSS": "%f",
    "SS": "%f",
    "S": "%f",  # ms → µs approximation
    # AM/PM
    "a": "%p",
    # Timezone
    "Z": "%z",
    "ZZ": "%z",
    "ZZZ": "%z",  # RFC 822:  -0800
    "X": "%z",
    "XX": "%z",
    "XXX": "%z",  # ISO 8601: -08 / -0800 / -08:00
    "z": "%Z",
    "zz": "%Z",
    "zzz": "%Z",
    "zzzz": "%Z",  # Timezone name (strptime unreliable)
    # Date fragments
    "D": "%j",
    "DD": "%j",
    "DDD": "%j",  # Day in year
    "w": "%U",
    "ww": "%U",  # Week in year, Sunday-based (%W = Monday-based)
    "u": "%u",  # Day-of-week number (1=Mon)
    # No Python equivalent — dropped silently so parsing still succeeds for other fields
    "W": "",
    "WW": "",  # Week in month
    "F": "",  # Day of week in month
    "G": "",
    "GG": "",
    "GGG": "",  # Era (e.g. "AD")
}


_PYTHON_FMT_RE = re.compile(r"%[A-Za-z%]")


def _convert_java_letter_token(token: str) -> str:
    """Return the Python strftime code for a single Java letter-sequence token.

    Looks up *token* in :data:`_JAVA_TOKEN_MAP`.  If not found (e.g. an
    unusually long repetition like ``"MMMMM"``), progressively tries shorter
    prefixes of the same letter so that Java's rule of "extra repetitions keep
    the same semantics as the longest documented repetition" is respected.
    """
    if token in _JAVA_TOKEN_MAP:
        return _JAVA_TOKEN_MAP[token]
    # Graceful fallback for repetitions longer than the longest map entry.
    letter = token[0]
    for length in range(len(token) - 1, 0, -1):
        key = letter * length
        if key in _JAVA_TOKEN_MAP:
            return _JAVA_TOKEN_MAP[key]
    return token  # Unknown pattern letter — pass through unchanged


def java_to_python_date_format(java_format: str) -> str:
    """Convert a Java ``SimpleDateFormat`` pattern to a Python ``strftime`` format string.

    The conversion handles:

    * All common Java date/time pattern letters (``y M d H h m s S E a Z z X …``).
    * Quoted literals — ``'T'`` becomes a literal ``T``; ``''`` becomes ``'``.
    * Standalone ``''`` outside quoted blocks → literal ``'``.
    * Literal ``%`` characters are escaped to ``%%``.
    * Unknown tokens are passed through unchanged (dateutil handles the rest).

    Examples::

        java_to_python_date_format("yyyy-MM-dd")                    # "%Y-%m-%d"
        java_to_python_date_format("yyyy-MM-dd HH:mm:ss")           # "%Y-%m-%d %H:%M:%S"
        java_to_python_date_format("dd.MM.yyyy 'T' HH:mm")          # "%d.%m.%Y T %H:%M"
        java_to_python_date_format("EEE, dd MMM yyyy")              # "%a, %d %b %Y"
        java_to_python_date_format("dd/MM/yy hh:mm:ss a")           # "%d/%m/%y %I:%M:%S %p"
        java_to_python_date_format("dd''MM")                        # "%d'%m"
        java_to_python_date_format("yyyy-MM-dd'T'HH:mm:ss.SSSXXX")  # "%Y-%m-%dT%H:%M:%S.%f%z"

    Args:
        java_format: A Java ``SimpleDateFormat`` pattern string.

    Returns:
        The equivalent Python ``strftime``/``strptime`` format string.
    """
    result: list[str] = []
    i = 0
    n = len(java_format)

    while i < n:
        c = java_format[i]

        if c == "'":
            # Standalone '' outside a quoted block → literal single-quote.
            if i + 1 < n and java_format[i + 1] == "'":
                result.append("'")
                i += 2
                continue

            # Quoted literal block: consume until closing single-quote.
            # A doubled '' inside the block is an escaped single-quote.
            i += 1
            while i < n:
                cc = java_format[i]
                if cc == "'":
                    if i + 1 < n and java_format[i + 1] == "'":
                        result.append("'")
                        i += 2
                    else:
                        i += 1  # closing quote
                        break
                else:
                    result.append(cc)
                    i += 1

        elif c == "%":
            # Escape literal % to avoid corrupting the Python format string.
            result.append("%%")
            i += 1

        elif c.isalpha():
            # Consume a run of the same letter, then look up the conversion.
            j = i + 1
            while j < n and java_format[j] == c:
                j += 1
            result.append(_convert_java_letter_token(java_format[i:j]))
            i = j

        else:
            result.append(c)
            i += 1

    return "".join(result)


def _is_python_strftime_format(fmt: str) -> bool:
    """Return ``True`` if *fmt* looks like a Python strftime format string.

    The heuristic searches for at least one ``%X`` directive (a ``%`` character
    followed by a letter or another ``%``). Python strftime strings always
    contain such directives, whereas Java ``SimpleDateFormat`` strings never
    use ``%``.
    """
    return bool(_PYTHON_FMT_RE.search(fmt))


def _to_python_strftime(date_format: str) -> str:
    """Return *date_format* as a Python ``strftime`` format string.

    If *date_format* already contains ``%X`` directives it is returned
    unchanged. Otherwise it is treated as a Java ``SimpleDateFormat`` string
    and converted via :func:`java_to_python_date_format`.
    """
    if _is_python_strftime_format(date_format):
        return date_format
    return java_to_python_date_format(date_format)


def _normalize_to_utc(dt: datetime) -> datetime:
    """Return *dt* as a timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date_string(date_string: str, date_format: str) -> datetime:
    """Parse *date_string* using the supplied format.

    *date_format* may be either a **Java SimpleDateFormat** string (e.g.
    ``yyyy-MM-dd HH:mm:ss``) or a **Python strftime** string (e.g.
    ``%Y-%m-%d %H:%M:%S``). The format type is detected automatically:
    strings that contain a ``%X`` directive are treated as Python strftime;
    all other strings are treated as Java ``SimpleDateFormat`` and converted
    before use.

    If the configured format fails to parse *date_string*, the function falls
    back to `dateutil.parser.parse` which attempts to guess the format
    automatically. A `UserWarning` is emitted so the issue remains visible.

    Args:
        date_string: The date string to parse.
        date_format: A date format string — either Java ``SimpleDateFormat`` or
            Python ``strftime`` notation (detected automatically).

    Returns:
        The parsed date as a timezone-aware `datetime.datetime` (UTC).

    Raises:
        ValueError: If the date string cannot be parsed by the configured
            format *or* by automatic detection.
    """

    python_format = _to_python_strftime(date_format)

    try:
        return _normalize_to_utc(datetime.strptime(date_string, python_format))  # noqa: DTZ007
    except (ValueError, TypeError):
        pass

    logger.warning(
        "Could not parse date string %r using format %r. "
        "Falling back to automatic date detection via dateutil.",
        date_string,
        date_format,
    )

    try:
        parsed = dateutil_parser.parse(date_string)
        return _normalize_to_utc(parsed)
    except (ParserError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"Could not parse date string {date_string!r} using format {date_format!r} "
            f"or by automatic detection."
        ) from exc
