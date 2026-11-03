from urllib.parse import parse_qs, unquote, urlparse


def as_bool(value):
    """python-decouple's bool cast treats the string "False" as true."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def csv_list(value):
    if value is None:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def is_database_url(value):
    return "://" in (value or "")


def database_from_url(url):
    """Parse a postgres URL. Require SSL when the host is not this machine."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote((parsed.path or "").lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": host,
        "PORT": str(parsed.port or ""),
    }
    query = parse_qs(parsed.query)
    if "sslmode" in query:
        config["OPTIONS"] = {"sslmode": query["sslmode"][-1]}
    elif host not in ("", "localhost", "127.0.0.1"):
        config["OPTIONS"] = {"sslmode": "require"}
    return config
