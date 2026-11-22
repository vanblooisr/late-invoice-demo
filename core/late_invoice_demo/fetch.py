"""Stage 1: finds late invoices and records a pending row for each.

Run: lid fetch  or  python -m late_invoice_demo.fetch
Needs: nothing with the fake adapter (no settings file is read, no key is read; only LID_DB_PATH
from the environment); MONEYBIRD_* in the environment or
the .env file in the current directory with the moneybird adapter.
"""

import argparse
import contextlib
import logging
import os
import sqlite3
import sys
from datetime import date

from .adapters import ADAPTER_NAMES, FakeBookkeeping, MoneybirdAdapter
from .adapters.fake import DEFAULT_FIXTURES_PATH
from .common import config, db
from .common.config import DEFAULT_DB_PATH
from .common.entry import parse_or_exit, run_guarded
from .common.log import install_redaction, redact
from .common.money import MoneyError, cents_to_str
from .common.ports import BookkeepingPort, Invoice

__all__ = ["fetch_late", "run", "add_arguments", "main"]

log = logging.getLogger(__name__)

# The one invoice state and the one currency this stage accepts.
LATE_STATE = "late"
CURRENCY = "EUR"
EXIT_OK = 0
EXIT_FAILED = 1
# The settings file read when it exists in the working directory.
SETTINGS_FILE = ".env"


def _problems(invoices: list[Invoice]) -> list[str]:
    """One line per offence in the batch; an empty list means the batch may be recorded."""
    found: list[str] = []
    for inv in invoices:
        if inv.state != LATE_STATE:
            found.append(f"invoice {inv.id} reports state {inv.state!r}, expected {LATE_STATE!r}")
        if inv.currency != CURRENCY:
            found.append(f"invoice {inv.id} is in currency {inv.currency!r}, expected {CURRENCY!r}")
        try:
            cents_to_str(inv.amount_cents)
            cents_to_str(inv.open_amount_cents)
        except MoneyError:
            found.append(f"invoice {inv.id} has an amount that is not integer cents")
        if type(inv.due_date) is not date:
            found.append(f"invoice {inv.id} has a due date that is not a calendar date")
    return found


def _fetch(conn: sqlite3.Connection, port: BookkeepingPort) -> tuple[list[Invoice], int, list[str]]:
    """Check the whole batch, then record it: (invoices, rows inserted, problems).

    With problems the table is untouched and the invoice list is empty.
    """
    invoices = port.list_late_invoices()
    problems = _problems(invoices)
    if problems:
        for line in problems:
            log.warning("fetch refused the batch: %s", line)
        return [], 0, problems
    rows = db.insert_pending_many(conn, invoices)
    for row in rows:
        log.info("fetch recorded row %d for invoice %s", row.id, row.invoice_id)
    return invoices, len(rows), []


def fetch_late(conn: sqlite3.Connection, port: BookkeepingPort) -> list[Invoice]:
    """Ask the port for late invoices and record a pending row for each that has none.

    The whole batch is checked before anything is written: every invoice must report the late state
    and the EUR currency, and carry integer-cent amounts and a calendar due date. If any invoice
    fails that check, nothing is recorded, the table is left exactly as it was, and each offending
    invoice is reported with a WARNING log line naming its id and the problem (fail closed).
    Otherwise the rows are inserted in one transaction (db.insert_pending_many): all land or none,
    and an error from the insert propagates with the table unchanged. The invoices in the batch are
    returned, whether or not their row was new. Rows that already exist are never updated, so
    running twice leaves the table unchanged. A refused batch returns an empty list. An error from
    the port propagates with the table unchanged.
    """
    invoices, _inserted, _problems_found = _fetch(conn, port)
    return invoices


def run(args: argparse.Namespace, *, port: BookkeepingPort | None = None) -> int:
    """Run this stage with the parsed arguments and return a process exit code.

    `port` is a seam for tests: None builds the adapter named by `args.adapter`; a port handed in
    is used as it is and is not closed here. The settings file (SETTINGS_FILE in the current
    directory) is read only for the moneybird adapter; a run with the fake adapter, or with a port
    handed in and the fake adapter named, reads one setting only, LID_DB_PATH from the process
    environment, and no key.

    Prints one summary line and one line per late invoice (number, due date, total, open amount,
    currency; never the customer) and returns 0. A refused batch, a missing setting or an error from
    the port prints one line to stderr naming the cause, leaves the table unchanged and returns 1.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    secrets: list[str] = []
    own_port: MoneybirdAdapter | None = None
    try:
        if args.adapter == "moneybird":
            settings = config.load(SETTINGS_FILE if os.path.isfile(SETTINGS_FILE) else None)
            config.require(settings, "moneybird_token", "moneybird_administration_id")
            secrets.append(settings.moneybird_token)
            install_redaction(secrets)
            if port is None:
                own_port = MoneybirdAdapter(
                    settings.moneybird_token, settings.moneybird_administration_id
                )
                port = own_port
        else:
            # The fake needs no keys, so the other settings (a Mollie key that is not a test key
            # would be refused by config.load) are not read. The config module has no function
            # for the database path alone, so that one name is read from the environment here and
            # handed to its public path resolver.
            settings = config.Settings(db_path=os.environ.get("LID_DB_PATH") or DEFAULT_DB_PATH)
            if port is None:
                port = FakeBookkeeping(DEFAULT_FIXTURES_PATH)
        with contextlib.closing(db.connect(config.resolve_db_path(args.db, settings))) as conn:
            db.init_schema(conn)
            invoices, inserted, problems = _fetch(conn, port)
    except Exception as exc:  # fail closed: any error is reported, never raised past the command
        print(f"fetch failed: {type(exc).__name__}: {redact(str(exc), secrets)}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        if own_port is not None:
            own_port.close()
    if problems:
        print("fetch refused the batch, nothing was recorded:", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        return EXIT_FAILED
    print(f"{len(invoices)} late invoice(s), {inserted} new row(s) recorded")
    for inv in invoices:
        print(
            f"{inv.invoice_number}  due {inv.due_date.isoformat()}  "
            f"total {cents_to_str(inv.amount_cents)}  open {cents_to_str(inv.open_amount_cents)} {inv.currency}"
        )
    return EXIT_OK


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
    """Entry point for `python -m late_invoice_demo.fetch`."""
    parser = argparse.ArgumentParser(prog="python -m late_invoice_demo.fetch")
    add_arguments(parser)
    r = parse_or_exit(parser, argv)
    if isinstance(r, int):
        return r
    return run_guarded(run, r, parser.prog)


if __name__ == "__main__":
    raise SystemExit(main())
