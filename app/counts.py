import re

_SUFFIXES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
_COUNT_RE = re.compile(r"([\d,]*\.?\d+)\s*([KMB]?)", re.IGNORECASE)


def parse_count(text: str) -> int:
    """Parse strings like '21.2M subscribers', '1.5K', '523', '14M views' into an int."""
    match = _COUNT_RE.search(text.strip())
    if not match or not match.group(1):
        raise ValueError(f"Could not parse count from: {text!r}")
    number = float(match.group(1).replace(",", ""))
    multiplier = _SUFFIXES.get(match.group(2).upper(), 1)
    return int(number * multiplier)


def format_count(n: int) -> str:
    """Format an int back into YouTube-style short form, e.g. 5650 -> '5.65K'."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        value, suffix = n / 1_000, "K"
    elif n < 1_000_000_000:
        value, suffix = n / 1_000_000, "M"
    else:
        value, suffix = n / 1_000_000_000, "B"
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}{suffix}"
