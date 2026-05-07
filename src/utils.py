from __future__ import annotations

import re
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso8601(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def from_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def discord_timestamp(dt: datetime, style: str = "F") -> str:
    unix_ts = int(dt.astimezone(timezone.utc).timestamp())
    return f"<t:{unix_ts}:{style}>"


def format_amount(amount: int, currency: str) -> str:
    return f"{amount:,} {currency}"


def parse_duration_to_minutes(value: str) -> int:
    normalized = value.strip().lower().replace(" ", "")
    if not normalized:
        raise ValueError("Time cannot be empty.")

    matches = re.findall(r"(\d+)([hm])", normalized)
    if not matches or "".join(f"{amount}{unit}" for amount, unit in matches) != normalized:
        raise ValueError("Use format like `30m`, `2h`, or `1h30m`.")

    total_minutes = 0
    for amount_text, unit in matches:
        amount = int(amount_text)
        if unit == "h":
            total_minutes += amount * 60
        else:
            total_minutes += amount

    if total_minutes <= 0:
        raise ValueError("Time must be greater than 0.")

    return total_minutes
