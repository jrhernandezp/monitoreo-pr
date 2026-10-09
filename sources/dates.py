"""Use Puerto Rico time consistently, regardless of the server timezone."""
from datetime import datetime, timedelta, timezone

PUERTO_RICO = timezone(timedelta(hours=-4), "America/Puerto_Rico")


def now_local():
    return datetime.now(PUERTO_RICO)


def parse_article_date(value):
    """Naive timestamps are PR local time; offset-bearing values are converted."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=PUERTO_RICO)
        return parsed.astimezone(PUERTO_RICO)
    except ValueError:
        return None


def browser_timestamp(value):
    # Date-only publications do not have a known hour.
    if not value or len(value) <= 10:
        return ""
    parsed = parse_article_date(value)
    return parsed.isoformat() if parsed else ""
