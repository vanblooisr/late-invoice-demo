"""Stage 2: sends the Telegram proposal with two buttons.

Run: lid approve  or  python -m late_invoice_demo.approve
Needs: TELEGRAM_* in .env (bot token, chat id and user id).

There is no --adapter flag: this stage never touches the bookkeeping port. It talks to Telegram only.
"""

import argparse
import sqlite3
from collections.abc import Callable
from datetime import date

from .common.config import DEFAULT_DB_PATH
from .common.entry import StageNotBuilt, parse_or_exit, run_guarded

__all__ = [
    "CALLBACK_MAX_BYTES",
    "CALLBACK_SEPARATOR",
    "CHOICES",
    "CHOICE_TO_STATUS",
    "parse_callback_data",
    "handle_callback",
    "send_proposals",
    "run",
    "add_arguments",
    "main",
]

# Telegram allows at most 64 bytes of callback_data per button, counted as UTF-8 bytes.
CALLBACK_MAX_BYTES = 64
# The wire format of callback_data: "<action id>:<choice>", for example "12:approve". The action id
# is the actions-table row id as ASCII digits with no sign, no spaces and no leading zero; the choice
# is one of CHOICES, exact case. The prefix handed to send() is "<action id>:" and the button appends
# its choice.
CALLBACK_SEPARATOR = ":"
CHOICES = ("approve", "reject")
# Which status a tap moves the row to; pending is the only status a tap can move from.
CHOICE_TO_STATUS = {"approve": "approved", "reject": "rejected"}


def parse_callback_data(data: str) -> tuple[int, str]:
    """Parse callback_data of the form "<action id>:<choice>" into (action id, choice).

    Raises ValueError when len(data.encode("utf-8")) > CALLBACK_MAX_BYTES, when there is not
    exactly one separator, when the id is not ASCII digits [1-9][0-9]* (so no sign, no spaces, no
    underscores, no other scripts' digits, not zero), or when the choice is not in CHOICES exactly.
    """
    raise StageNotBuilt("approve.parse_callback_data is not implemented")


def handle_callback(
    conn: sqlite3.Connection,
    chat_id: str,
    user_id: str,
    data: str,
    allowed_chat_id: str,
    allowed_user_id: str,
) -> bool:
    """Apply one button tap to the actions table.

    `chat_id` and `user_id` are the chat and the person the tap came from; `allowed_chat_id` and
    `allowed_user_id` are the configured ones. Checks, in order: both allowed ids are non-empty and
    both tapping ids equal them (an empty allowed id refuses every tap: the gate fails closed, and
    a right chat with a wrong person is refused the same as a wrong chat); `data` parses (a parse
    failure is refused, never raised); the action id names a row; the row is still pending. Any
    failed check is a WARNING log line naming the chat id, user id or action id and the reason, and
    returns False with the table unchanged. Otherwise the status moves pending ->
    CHOICE_TO_STATUS[choice] as one compare-and-set, the move is logged at INFO with the row id,
    and True is returned.
    """
    raise StageNotBuilt("approve.handle_callback is not implemented")


def send_proposals(
    conn: sqlite3.Connection,
    send: Callable[[str, str], None],
    *,
    today: date | None = None,
) -> int:
    """Send one message per pending row whose messaged_at is empty; return how many were sent.

    `send(text, callback_prefix)` delivers one message with two buttons and is called positionally,
    as send(text, callback_prefix), never with keywords, so any callable taking two positional
    arguments serves; the text names the invoice
    number, both the total (amount_cents) and the open amount (open_amount_cents) of the row, each
    as common/money.py formats it, and how many days late the invoice is:
    `today` minus the row's due_date, in whole days. `today` is a calendar date; None means
    today's date in UTC, so tests pass a fixed date. `callback_prefix` is "<row id>:" so each
    button's callback_data is the prefix plus its choice. messaged_at is written through
    db.mark_messaged only after send() returns, so a send that raised is retried on the next run and
    a sent one is not repeated; a crash between the return and the write re-sends that one row once.
    A send() that raises stops this run after logging the failure; the rows already sent stay marked.
    """
    raise StageNotBuilt("approve.send_proposals is not implemented")


def run(args: argparse.Namespace) -> int:
    """Run this stage with the parsed arguments and return a process exit code."""
    raise StageNotBuilt("approve.run is not implemented")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add this stage's own flags to `parser`."""
    parser.add_argument(
        "--db",
        default=None,
        help=f"SQLite file for the actions table (default: {DEFAULT_DB_PATH}, resolved via config)",
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m late_invoice_demo.approve`."""
    parser = argparse.ArgumentParser(prog="python -m late_invoice_demo.approve")
    add_arguments(parser)
    r = parse_or_exit(parser, argv)
    if isinstance(r, int):
        return r
    return run_guarded(run, r, parser.prog)


if __name__ == "__main__":
    raise SystemExit(main())
