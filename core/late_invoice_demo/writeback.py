"""Stage 4: checks the payment and books it in the bookkeeping system.

Run: lid check (alias: lid writeback)  or  python -m late_invoice_demo.writeback
Needs: MOLLIE_TEST_KEY in .env; MONEYBIRD_* in .env with the moneybird adapter.
"""

import argparse
import sqlite3
import time
from collections.abc import Callable

from .adapters import ADAPTER_NAMES
from .common.config import DEFAULT_DB_PATH
from .common.entry import StageNotBuilt, parse_or_exit, run_guarded
from .common.mollie import MollieClient
from .common.ports import BookkeepingPort

__all__ = [
    "WAIT_TIMEOUT_SECONDS",
    "POLL_INTERVAL_PLACEHOLDER_SECONDS",
    "WAIT_PAID",
    "WAIT_TIMED_OUT",
    "WAIT_CANCELLED",
    "check_payments",
    "wait_for_payment",
    "run",
    "add_arguments",
    "main",
]

# How long the wait for a payment lasts before it gives up: 5 minutes.
WAIT_TIMEOUT_SECONDS = 300.0
# PLACEHOLDER. The poll interval is not decided; this value only gives the parameter a default and
# is not a production choice. API-NOTES.md (i) says the interval is chosen from the RateLimit-Policy
# header of the first real response.
POLL_INTERVAL_PLACEHOLDER_SECONDS = 5.0
# The three outcomes of the wait.
WAIT_PAID = "paid"
WAIT_TIMED_OUT = "timed_out"
WAIT_CANCELLED = "cancelled"


def wait_for_payment(
    mollie: MollieClient,
    link_id: str,
    poll_interval_seconds: float = POLL_INTERVAL_PLACEHOLDER_SECONDS,
    *,
    timeout_seconds: float = WAIT_TIMEOUT_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Block until the payment link is paid, the wait times out, or the user cancels; return which.

    Returns WAIT_PAID as soon as a read of the link (mollie.get_payment_link) shows it paid,
    WAIT_TIMED_OUT once `timeout_seconds` (default WAIT_TIMEOUT_SECONDS, 5 minutes) have passed on
    `clock` since the call without a paid read, and WAIT_CANCELLED when KeyboardInterrupt (Ctrl-C)
    arrives during a read or a sleep: the interrupt is caught here and not re-raised. The link is
    read first and slept after, so an already paid link returns without sleeping.

    The wait only reads. It never writes the actions table and never books: on a timeout or a
    cancel the row stays link_created, for a later check_payments run to resolve.

    The reads inside the wait follow the one retry policy with the remaining time budget (the
    `timeout_seconds` not yet used, on `clock`) passed as its Retry-After cap, so a rate-limit
    answer that asks for longer than the wait has left is not waited for and is re-raised.

    `poll_interval_seconds` is the pause between two reads. It is a parameter on purpose: the
    interval is NOT decided. The default is POLL_INTERVAL_PLACEHOLDER_SECONDS, a placeholder and not
    a production value. `clock` (monotonic seconds) and `sleep(seconds)` are injectable so tests
    need no real time.
    """
    raise StageNotBuilt("writeback.wait_for_payment is not implemented")


def check_payments(
    conn: sqlite3.Connection,
    port: BookkeepingPort,
    mollie: MollieClient,
    send: Callable[[str], None] | None = None,
) -> int:
    """Book every paid link once and return how many payments were booked.

    First, every row found in `booking` at the start of the run moves booking -> booking_unconfirmed
    and is reported (log and `send`): an earlier booking attempt ended without a recorded result, so
    the payment may or may not be booked. Such a row is never booked, and its invoice is not read.

    Runs are sequential: one `check` run at a time. The claim below guards against a repeated or
    an interrupted run; running two at once is not supported.

    Then only rows whose status is link_created are considered; a row in any other status is never
    booked, whatever link it holds. For each row the link is read from Mollie and the invoice is
    re-fetched through the port, in that order. The checks run in this order:

    1. Invoice no longer unpaid (settled another way): nothing is booked. "No longer unpaid" means
       Invoice.open_amount_cents == 0; the vendor's state string is not the rule, so a state that
       still reads late with nothing open counts as paid, and an open amount above 0 counts as
       unpaid whatever the state says. The row moves
       link_created -> paid_elsewhere, the link is archived so it cannot be paid again, and the case
       is reported in the log and through `send` ("customer paid twice — refund needed" when the
       link was paid as well, "invoice settled elsewhere, link closed" when it was not).
    2. Link paid and invoice still unpaid: the paid amount must equal the invoice's OPEN amount
       (Invoice.open_amount_cents, not the total), cents to cents (a mismatch of one cent either
       way is a mismatch). A mismatch books nothing, moves the row link_created -> amount_mismatch
       and is reported with both amounts.
    3. Claim: the row moves link_created -> booking as one compare-and-set (db.set_status). Only the
       run for which that returns True goes on; a run that lost the claim books nothing.
    4. Book: the claiming run calls the port's register_payment, once, with the link's paid time as
       payment date, then moves booking -> paid as one
       compare-and-set and confirms through `send` ("Betaald"). register_payment is never retried:
       it is not idempotent. A failure inside it is reported and the row stays in `booking`; the
       next run finds it there and moves it to booking_unconfirmed (see above), so a payment whose
       result is unknown is never booked twice.

    Link unpaid and invoice unpaid: nothing changes and the row stays link_created. A link that ran
    out unpaid moves the row link_created -> link_expired and is reported; how an ended link shows
    on the wire is not stated in API-NOTES.md, so the detection rule is an open detail. Running
    twice, in sequence, books once.

    Connection and timeout failures on the reads (the link, the invoice) follow the one retry
    policy; after the last attempt the row is left unchanged and the cancel is reported. Any reply
    the code does not recognise leaves the row as it was (fail closed).
    """
    raise StageNotBuilt("writeback.check_payments is not implemented")


def run(args: argparse.Namespace) -> int:
    """Run this stage with the parsed arguments and return a process exit code."""
    raise StageNotBuilt("writeback.run is not implemented")


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
    """Entry point for `python -m late_invoice_demo.writeback`."""
    parser = argparse.ArgumentParser(prog="python -m late_invoice_demo.writeback")
    add_arguments(parser)
    r = parse_or_exit(parser, argv)
    if isinstance(r, int):
        return r
    return run_guarded(run, r, parser.prog)


if __name__ == "__main__":
    raise SystemExit(main())
