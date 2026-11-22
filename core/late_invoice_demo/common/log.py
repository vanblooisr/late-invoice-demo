"""One redaction rule, applied where a log record is made so a record from any logger is covered.

Two hooks carry it. The log-record factory redacts the message, its %-arguments, the traceback and
the stack text. A wrapper around `logging.Logger.makeRecord` redacts every string value the caller
passed in `extra=`, on the finished record. Both hold for every logger and for a handler attached
before or after install_redaction. `uninstall_redaction` puts both hooks back.
"""

import functools
import logging
import re
from collections.abc import Callable, Sequence

__all__ = ["REDACTED", "redact", "install_redaction", "uninstall_redaction"]

REDACTED = "[REDACTED]"

# An Authorization header (or JSON field): its name and scheme are kept, the credential goes.
_AUTHORIZATION = re.compile(
    r"""(\bauthorization["']?\s*[:=]\s*["']?(?:(?:bearer|basic|digest|negotiate)\s+)?)[^\s,;"']+""",
    re.IGNORECASE,
)
# "Bearer <token>" outside a header. The word also occurs in prose ("the bearer of news"), so a
# short all-letter word after it is left alone; a token of 8 or more characters, or any token
# holding a digit or a symbol, is redacted.
_BEARER = re.compile(r"\b(bearer)\s+([^\s,;\"']+)", re.IGNORECASE)
_BEARER_MIN_PLAIN_LENGTH = 8
# A name that holds a key word, then ":" or "=" (with optional quotes and spaces) and its value; the
# name and the separator are kept, the value goes. The name is checked by _is_secret_name.
# The value is a double-quoted or single-quoted run (spaces allowed), or an unquoted run that goes to
# the end of the line or the next "," ";" "&" or closing bracket/brace, spaces included; an opening
# quote with no closing one still redacts the run after it.
_KEYED_VALUE = re.compile(
    r"""(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]*(?:key|token|secret|password|passwd|pwd)[A-Za-z0-9_.-]*)"""
    r"""(["']?\s*[:=]\s*)("[^"]*"|'[^']*'|["']?[^\s&,;)\]}"'][^&,;)\]}"'\r\n]*)""",
    re.IGNORECASE,
)
_NAME_WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+")
# A name is a key name when ANY of its words is one of these, or ends in one of the longer ones (a
# one-word compound such as `dbpassword`), or is a known compound of key (`apikey`). `key` alone is
# not a valid ending of a longer word: `monkey` and `turkey` are not keys.
_KEY_WORDS = frozenset({"key", "token", "secret", "password", "passwd", "pwd"})
_KEY_ENDINGS = ("token", "secret", "password", "passwd", "pwd")
_KEY_COMPOUND = re.compile(r"(?:api|access|auth|secret|private|client|refresh|bot|app)key", re.IGNORECASE)
# Credentials in URL userinfo: scheme://user:password@host; the password goes, user and host stay.
_URL_USERINFO = re.compile(r"(\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@?#]+:)[^\s/@?#]+(?=@)")
# The Telegram token sits in the path after the API host and "bot" (or "file/bot" for downloads).
_TELEGRAM_BOT = re.compile(r"(api\.telegram\.org/(?:file/)?bot)[^/\s?#]+", re.IGNORECASE)
_LONG_RUN = re.compile(r"[A-Za-z0-9_-]{24,}")

# What was in place before install_redaction first wrapped it; None while nothing is installed.
_original_factory: Callable[..., logging.LogRecord] | None = None
_original_make_record: Callable[..., logging.LogRecord] | None = None
# The secrets the makeRecord wrapper applies; replaced by each install_redaction call.
_secrets: tuple[str, ...] = ()


def redact(text: str, secrets: Sequence[str] = ()) -> str:
    """Return `text` with secrets replaced by REDACTED.

    Replaces:
    - every exact value in `secrets`
    - the credential of an `Authorization` header or field (any scheme, `Basic` included)
    - `Bearer <token>` outside a header
    - the value after a name with ANY word that is key, token, secret, password, passwd or pwd (or a
      one-word compound ending in token, secret, password, passwd or pwd, or `apikey`-style), in a
      query string, a header (`X-Api-Key: abc`), an assignment (`api_key = abc`, `myToken=abc`) or
      JSON (`"token": "abc"`); a quoted value is taken whole, spaces included, an unquoted one runs
      to the end of the line or the next `,` `;` `&` or closing bracket/brace. A name that only
      contains those letters in one lowercase word (`monkey`, `keyboard`) is left alone; a name
      with a key word anywhere (`primary key`, `sort_key`, `token_count`, `clientKeyValue`) is
      redacted too, on purpose
    - the password in URL userinfo (`https://user:pw@host/`); user and host stay
    - the Telegram path segment after `api.telegram.org/bot`
    - any long token-like run (24 or more characters of [A-Za-z0-9_-])
    """
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = _AUTHORIZATION.sub(lambda m: m.group(1) + REDACTED, text)
    text = _BEARER.sub(_redact_bearer, text)
    text = _URL_USERINFO.sub(lambda m: m.group(1) + REDACTED, text)
    text = _KEYED_VALUE.sub(_redact_keyed_value, text)
    text = _TELEGRAM_BOT.sub(lambda m: m.group(1) + REDACTED, text)
    return _LONG_RUN.sub(REDACTED, text)


def _redact_bearer(match: re.Match) -> str:
    """Redact the token after "Bearer", unless it is a short plain word (prose)."""
    token = match.group(2)
    if len(token) < _BEARER_MIN_PLAIN_LENGTH and token.isascii() and token.isalpha():
        return match.group(0)
    return f"{match.group(1)} {REDACTED}"


def _is_secret_name(name: str) -> bool:
    """True when any word of the name is a key word (fails closed).

    Words split at a separator or a case change, so `api_key`, `X-Api-Key`, `apiKey`, `myToken`,
    `key2`, `secret_key_base` and `token_type` count, as do one-word compounds like `dbpassword`;
    `monkey` and `keyboard` do not.
    """
    words = _NAME_WORD.findall(name)
    for word in words:
        lower = word.lower()
        if lower in _KEY_WORDS or lower.endswith(_KEY_ENDINGS) or _KEY_COMPOUND.fullmatch(lower):
            return True
    return False


def _redact_keyed_value(match: re.Match) -> str:
    """Redact the value after a key-like name; leave a name that only contains the letters alone."""
    if not _is_secret_name(match.group(1)):
        return match.group(0)
    value = match.group(3)
    if value[0] in "\"'":
        closed = len(value) >= 2 and value[-1] == value[0]
        shown = value[0] + REDACTED + (value[0] if closed else "")
    else:
        shown = REDACTED
    return match.group(1) + match.group(2) + shown


def install_redaction(secrets: Sequence[str]) -> None:
    """Redact every log record when it is created and raise httpx and httpcore to WARNING.

    Two hooks, each installed once however often this is called:
    - the log-record factory redacts the message, its %-arguments, the traceback and the stack text;
    - a wrapper around `logging.Logger.makeRecord` redacts, on the finished record, every `extra=`
      value that is a str.
    Both apply to a record from any logger (the root, httpx, httpcore, telegram) and to any handler,
    attached before or after this call. Calling it again replaces the secret list; it does not stack
    a second wrapper. `uninstall_redaction` restores both hooks.

    NOT covered: a non-string `extra=` value (a number, a dict, an object holding a secret is
    stored as given); an attribute set on a record after creation (`record.detail = ...` in a
    filter or handler); a record built by `logging.makeLogRecord` (it bypasses both hooks), or by a
    Logger subclass whose makeRecord does not call the wrapped method.
    """
    global _original_factory, _original_make_record, _secrets
    known = tuple(s for s in secrets if s)
    _secrets = known
    if _original_factory is None:
        _original_factory = logging.getLogRecordFactory()
    base = _original_factory

    def factory(*args, **kwargs) -> logging.LogRecord:
        return _scrub(base(*args, **kwargs), known)

    factory._redacts_message = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)

    if _original_make_record is None:
        _original_make_record = logging.Logger.makeRecord
        logging.Logger.makeRecord = _wrap_make_record(_original_make_record)

    for name in ("httpx", "httpcore"):
        logger = logging.getLogger(name)
        if logger.getEffectiveLevel() < logging.WARNING:
            logger.setLevel(logging.WARNING)


def uninstall_redaction() -> None:
    """Put back the record factory and Logger.makeRecord that install_redaction replaced; a no-op when none."""
    global _original_factory, _original_make_record, _secrets
    if _original_make_record is not None:
        logging.Logger.makeRecord = _original_make_record
        _original_make_record = None
    if _original_factory is not None:
        logging.setLogRecordFactory(_original_factory)
        _original_factory = None
    _secrets = ()


def _wrap_make_record(original: Callable[..., logging.LogRecord]) -> Callable[..., logging.LogRecord]:
    """Logger.makeRecord that redacts each str value of `extra` on the record the original returns."""

    @functools.wraps(original)
    def make_record(
        self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None
    ) -> logging.LogRecord:
        record = original(self, name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)
        for key, value in (extra or {}).items():
            if isinstance(value, str) and key in record.__dict__:
                record.__dict__[key] = redact(value, _secrets)
        return record

    make_record._redacts_extra = True  # type: ignore[attr-defined]
    return make_record


def _scrub(record: logging.LogRecord, secrets: Sequence[str]) -> logging.LogRecord:
    """Replace the record's message, traceback and stack text by their redacted form."""
    try:
        message = record.getMessage()
    except Exception:
        # Arguments that do not fit the format, or an argument whose str() fails: keep the format
        # text only, never the arguments. A logging call never raises into its caller.
        try:
            message = str(record.msg)
        except Exception:
            message = "<log message could not be formatted>"
    record.msg = redact(message, secrets)
    record.args = ()
    if record.exc_info and record.exc_info[0] is not None:
        formatted = logging.Formatter().formatException(record.exc_info)
        record.exc_text = redact(formatted, secrets)
        record.exc_info = None
    if record.stack_info:
        record.stack_info = redact(record.stack_info, secrets)
    return record
