"""The one money formatter and parser.

Amounts are integer cents everywhere. Negatives are rejected on both sides, because a credit
never becomes a payment link.

Grammar:
- `cents_to_str` takes an int >= 0 and < MAX_CENTS (bool is rejected: it is an int subclass) and
  returns digits, a dot, and exactly two decimals (12100 -> "121.00").
- `str_to_cents` accepts exactly AMOUNT_PATTERN, applied with re.fullmatch (ASCII digits only; a
  trailing newline is rejected): no sign, no comma, no thousands separator, no
  whitespace, no currency symbol, no missing or extra decimals. It returns int cents, which must
  be below MAX_CENTS; a longer digit string is refused before it is converted to an int.
- Anything else raises MoneyError.
"""

import re

__all__ = ["AMOUNT_PATTERN", "MAX_CENTS", "MoneyError", "cents_to_str", "str_to_cents"]

AMOUNT_PATTERN = r"\A[0-9]+\.[0-9]{2}\Z"
# Amounts are below this many cents (exclusive), in both directions.
MAX_CENTS = 10**15
# The most digits a whole part below MAX_CENTS can have (MAX_CENTS is 10**13 whole units).
_MAX_WHOLE_DIGITS = 13


class MoneyError(ValueError):
    """Raised for an amount that is not valid integer cents or a string that is not a valid amount."""


def cents_to_str(amount_cents: int) -> str:
    """Format integer cents (>= 0, not bool) as a decimal string, for example 12100 as "121.00"."""
    if type(amount_cents) is not int:
        raise MoneyError(f"amount must be an int of cents, not {type(amount_cents).__name__}")
    if amount_cents < 0:
        raise MoneyError("amount must not be negative")
    if amount_cents >= MAX_CENTS:
        raise MoneyError("amount is too large")
    whole, cents = divmod(amount_cents, 100)
    return f"{whole}.{cents:02d}"


def str_to_cents(text: str) -> int:
    """Parse a string matching AMOUNT_PATTERN into integer cents, for example "121.00" as 12100."""
    if not isinstance(text, str) or re.fullmatch(AMOUNT_PATTERN, text) is None:
        raise MoneyError("amount is not a plain two-decimal string")
    whole, _, cents = text.partition(".")
    # Judge the size on the digits before int() sees them: int() refuses a very long string.
    significant = whole.lstrip("0")
    if len(significant) > _MAX_WHOLE_DIGITS:
        raise MoneyError("amount is too large")
    amount_cents = int(significant or "0") * 100 + int(cents)
    if amount_cents >= MAX_CENTS:
        raise MoneyError("amount is too large")
    return amount_cents
