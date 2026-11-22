"""Settings come from the environment or a local .env file; nothing is ever logged from here."""

import os
from dataclasses import dataclass, fields

from dotenv import dotenv_values

__all__ = ["DEFAULT_DB_PATH", "ConfigError", "Settings", "load", "require", "resolve_db_path"]

DEFAULT_DB_PATH = "late_invoice_demo.db"

# Settings field -> the environment variable it is read from.
# A vendor setting is read from the variable that is its field name in capitals; the database path
# has its own prefixed name.
_VENDOR_FIELDS = (
    "moneybird_token",
    "moneybird_administration_id",
    "mollie_test_key",
    "telegram_bot_token",
    "telegram_chat_id",
    "telegram_user_id",
)
_ENV_NAMES = {name: name.upper() for name in _VENDOR_FIELDS} | {"db_path": "LID_DB_PATH"}
_MOLLIE_TEST_PREFIX = "test_"


class ConfigError(ValueError):
    """Raised for a missing required variable or a value that breaks a rule."""


@dataclass(frozen=True)
class Settings:
    """All configuration the stages need. Most values are secrets; no value is ever shown in repr."""

    # None until load() fills it; a stage asks for what it needs via require().
    moneybird_token: str | None = None  # MONEYBIRD_TOKEN (secret)
    moneybird_administration_id: str | None = None  # MONEYBIRD_ADMINISTRATION_ID
    # MOLLIE_TEST_KEY (secret). A Mollie TEST key by rule: live keys are refused.
    mollie_test_key: str | None = None
    telegram_bot_token: str | None = None  # TELEGRAM_BOT_TOKEN (secret)
    telegram_chat_id: str | None = None  # TELEGRAM_CHAT_ID
    # TELEGRAM_USER_ID: the one person whose button taps are accepted, next to the chat id.
    telegram_user_id: str | None = None
    db_path: str = DEFAULT_DB_PATH  # env LID_DB_PATH (optional)

    # Only repr and str are masked: dataclasses.asdict, vars and pickling still expose values.
    def __repr__(self) -> str:
        """Show field names only, never values, so a stray print cannot leak a secret."""
        names = ", ".join(f.name for f in fields(self))
        return f"Settings({names})"


def load(dotenv_path: str | None = None) -> Settings:
    """Build Settings from the environment, reading `dotenv_path` first when given.

    A process environment variable overrides the same key in the .env file. load never fails on
    a missing variable by itself: it returns None fields and stages call require(). A
    MOLLIE_TEST_KEY that does not start with `test_` raises ConfigError.
    """
    values = _read_values(dotenv_path)
    key = values.get("mollie_test_key")
    if key is not None and not key.startswith(_MOLLIE_TEST_PREFIX):
        # Drop the raw values before raising, so a traceback that prints local variables shows none.
        del values, key
        # The message names the variable and the rule, never the value.
        raise ConfigError(f"MOLLIE_TEST_KEY must start with {_MOLLIE_TEST_PREFIX!r}: a test key only")
    return Settings(**values)


def _read_values(dotenv_path: str | None) -> dict[str, str]:
    """The set values by Settings field name: the process environment over the .env file."""
    from_file = dotenv_values(dotenv_path) if dotenv_path is not None else {}
    values: dict[str, str] = {}
    for field_name, env_name in _ENV_NAMES.items():
        # An empty value counts as unset in both places, so an empty line in the file or an empty
        # exported variable does not mask the other source.
        value = os.environ.get(env_name) or from_file.get(env_name) or None
        if value is not None:
            values[field_name] = value
    return values


def require(settings: Settings, *names: str) -> None:
    """Check that the named Settings fields are set.

    Raises ConfigError naming the first missing variable, so a stage with the fake adapter never
    needs keys.
    """
    for name in names:
        env_name = _ENV_NAMES.get(name)
        if env_name is None:
            raise ValueError(f"unknown setting {name!r}")
        if not getattr(settings, name):
            raise ConfigError(f"{env_name} is not set")


def resolve_db_path(flag: str | None, settings: Settings | None = None) -> str:
    """Return the database path as an absolute path.

    Precedence: the --db flag, then Settings.db_path, then DEFAULT_DB_PATH.
    """
    chosen = flag or (settings.db_path if settings is not None else None) or DEFAULT_DB_PATH
    return os.path.abspath(chosen)
