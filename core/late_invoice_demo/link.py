"""Stage 3: creates the payment link for an approved invoice.

Run: lid link  or  python -m late_invoice_demo.link
Needs: MOLLIE_TEST_KEY in .env; MONEYBIRD_* in .env with the moneybird adapter.

The adapter here is the bookkeeping side (it reads the approved invoice); the payment link itself
comes from Mollie, a direct client.
"""

import argparse
import sqlite3
from collections.abc import Callable

from .adapters import ADAPTER_NAMES
from .common.config import DEFAULT_DB_PATH
from .common.entry import StageNotBuilt, parse_or_exit, run_guarded
from .common.mollie import MollieClient
from .common.ports import BookkeepingPort

__all__ = ["idempotency_key", "create_links", "run", "add_arguments", "main"]


def idempotency_key(invoice_id: str, action_id: int) -> str:
    """Return the Idempotency-Key for one row: "<invoice id>-<row id>".

    Both parts are needed: the row id alone restarts when the database is recreated, and the
    invoice id alone repeats when the same invoice is fetched into a new row. The key is the same
    on every attempt and every run for one row, and differs between rows.
    """
    raise StageNotBuilt("link.idempotency_key is not implemented")


def create_links(
    conn: sqlite3.Connection,
    port: BookkeepingPort,
    mollie: MollieClient,
    send: Callable[[str], None] | None = None,
) -> int:
    """Create one payment link per approved row and return how many were created.

    Per approved row: re-fetch the invoice through the port; an invoice that is no longer unpaid
    (Invoice.open_amount_cents == 0; the vendor's state string is not the rule, so a state that
    still reads late with nothing open counts as paid) gets no link, the row moves approved -> paid_elsewhere, and the case is reported with a WARNING
    line naming the invoice. Otherwise POST the link for the invoice's OPEN amount
    (Invoice.open_amount_cents, not the total, so a partly paid invoice is charged what is still
    owed) as common/money.py formats it, a description
    naming the invoice number, an expiry of the row's created_at + LINK_LIFETIME (derived from the
    row, not from the clock, so every retry and re-run sends the same body), and the Idempotency-Key
    from idempotency_key(). Within Mollie's one-hour key window a retried or re-run POST returns the same
    link; after that window the stored link id is the guard, so a row whose POST was lost and that
    is retried later than an hour can get a second link, and that case is reported when the amount
    (the open amount) or description of the returned link does not match the row. Connection and timeout failures
    follow the one retry policy; after the last attempt the row is left unchanged and the cancel is
    reported as "connection failed after 3 attempts" naming the invoice. Success stores the link id
    and url and moves approved -> link_created through db.set_link, one compare-and-set, and sends
    the link url through `send` when one is given (the Telegram message of this stage).
    """
    raise StageNotBuilt("link.create_links is not implemented")


def run(args: argparse.Namespace) -> int:
    """Run this stage with the parsed arguments and return a process exit code."""
    raise StageNotBuilt("link.run is not implemented")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add this stage's own flags to `parser`."""
    parser.add_argument(
        "--adapter",
        choices=ADAPTER_NAMES,
        default="fake",
        help="bookkeeping adapter: fake reads local fixtures and needs no keys; "
        "moneybird talks to one sandbox administration",
    )
    parser.add_argument(
        "--db",
        default=None,
        help=f"SQLite file for the actions table (default: {DEFAULT_DB_PATH}, resolved via config)",
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m late_invoice_demo.link`."""
    parser = argparse.ArgumentParser(prog="python -m late_invoice_demo.link")
    add_arguments(parser)
    r = parse_or_exit(parser, argv)
    if isinstance(r, int):
        return r
    return run_guarded(run, r, parser.prog)


if __name__ == "__main__":
    raise SystemExit(main())
