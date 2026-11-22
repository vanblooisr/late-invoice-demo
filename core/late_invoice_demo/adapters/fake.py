"""A bookkeeping adapter that serves invoices from a local JSON fixtures file, for demos and tests.

The fixtures are loaded into memory on first use and the four verbs are served from that store,
so a registered payment is visible to later reads within one adapter. `fixtures_path` is a path to
ONE JSON file (invoices and contacts) that you trust; it is read as data only. Construction only
stores the path.

DEFAULT_FIXTURES_PATH is the sample data that ships inside this package, in
adapters/sample_data/invoices.json: six invented invoices and three invented contacts. An install
of the package carries it, so the default works without any other folder.

The file holds `invoices` (id, invoice_number, contact_id, contact_name, amount, open_amount,
currency, due_date, state) and `contacts` (id, name, email). Amounts are two-decimal strings read
through common/money.py. Each invoice is held to the field rules the Moneybird adapter applies to
vendor data (the rule objects are imported from there, so the two cannot drift): the id is ASCII
digits, the state is one of the vendor's known states, the currency is three capitals, the due date
is YYYY-MM-DD and a real date, and the open amount is not above the total. An empty contact email
reads as None. A file that is missing a field, repeats an id or breaks one of these rules raises
ValueError when it is first used.

Where the two adapters differ on purpose: this one refuses an overpayment itself (and a payment on
an invoice with nothing open) with ValueError, while the Moneybird adapter sends the amount and
the vendor decides. This one supports get_contact; the Moneybird adapter raises UnsupportedVerb.
"""

import json
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

from ..common.money import MoneyError, cents_to_str, str_to_cents
from ..common.ports import Contact, Invoice, PaymentReceipt
from .moneybird import CURRENCY_PATTERN, DATE_PATTERN, ID_PATTERN, INVOICE_STATES

__all__ = ["DEFAULT_FIXTURES_PATH", "FakeBookkeeping"]

DEFAULT_FIXTURES_PATH = Path(__file__).resolve().parent / "sample_data" / "invoices.json"

# The vendor state of an invoice that has been settled in full.
_PAID_STATE = "paid"
_LATE_STATE = "late"


def _text(raw: dict, key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"fixtures: {where} lacks a text field {key!r}")
    return value


def _invoice_from(raw: object) -> Invoice:
    if not isinstance(raw, dict):
        raise ValueError("fixtures: an invoice entry is not an object")
    where = f"invoice {raw.get('id')!r}"
    invoice_id = _text(raw, "id", where)
    if ID_PATTERN.fullmatch(invoice_id) is None:
        raise ValueError(f"fixtures: {where} has an id that is not a string of digits")
    state = _text(raw, "state", where)
    if state not in INVOICE_STATES:
        raise ValueError(f"fixtures: {where} has an unrecognised state {state!r}")
    currency = _text(raw, "currency", where)
    if CURRENCY_PATTERN.fullmatch(currency) is None:
        raise ValueError(f"fixtures: {where} has a currency in an unrecognised shape")
    due = _text(raw, "due_date", where)
    if DATE_PATTERN.fullmatch(due) is None:
        raise ValueError(f"fixtures: {where} has a due_date in an unrecognised shape")
    try:
        amount = str_to_cents(_text(raw, "amount", where))
        open_amount = str_to_cents(_text(raw, "open_amount", where))
        due_date = date.fromisoformat(due)
    except (MoneyError, ValueError) as exc:
        raise ValueError(f"fixtures: {where} has a field in an unrecognised shape") from exc
    if open_amount > amount:
        raise ValueError(f"fixtures: {where} has more open than its total")
    return Invoice(
        id=invoice_id,
        invoice_number=_text(raw, "invoice_number", where),
        contact_id=_text(raw, "contact_id", where),
        contact_name=_text(raw, "contact_name", where),
        amount_cents=amount,
        open_amount_cents=open_amount,
        currency=currency,
        due_date=due_date,
        state=state,
    )


def _contact_from(raw: object) -> Contact:
    if not isinstance(raw, dict):
        raise ValueError("fixtures: a contact entry is not an object")
    where = f"contact {raw.get('id')!r}"
    email = raw.get("email")
    if email is not None and not isinstance(email, str):
        raise ValueError(f"fixtures: {where} has an email that is not text")
    return Contact(id=_text(raw, "id", where), name=_text(raw, "name", where), email=email or None)


class FakeBookkeeping:
    """Implements BookkeepingPort against local fixtures instead of a real vendor."""

    def __init__(self, fixtures_path: str | os.PathLike[str]) -> None:
        self.fixtures_path = os.fspath(fixtures_path)
        self._invoices: dict[str, Invoice] | None = None
        self._contacts: dict[str, Contact] = {}
        self._payments = 0

    def _load(self) -> dict[str, Invoice]:
        if self._invoices is None:
            with open(self.fixtures_path, encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("fixtures: the file is not an object")
            invoices: dict[str, Invoice] = {}
            for raw in data.get("invoices", []):
                invoice = _invoice_from(raw)
                if invoice.id in invoices:
                    raise ValueError(f"fixtures: invoice id {invoice.id!r} appears twice")
                invoices[invoice.id] = invoice
            contacts: dict[str, Contact] = {}
            for raw in data.get("contacts", []):
                contact = _contact_from(raw)
                if contact.id in contacts:
                    raise ValueError(f"fixtures: contact id {contact.id!r} appears twice")
                contacts[contact.id] = contact
            self._contacts = contacts
            self._invoices = invoices
        return self._invoices

    def list_late_invoices(self) -> list[Invoice]:
        """Return invoices the bookkeeping system itself reports as late (its own late state), not a due-date computed here."""
        return [i for i in self._load().values() if i.state == _LATE_STATE]

    def get_invoice(self, invoice_id: str) -> Invoice:
        """Return one invoice by id."""
        try:
            return self._load()[invoice_id]
        except KeyError:
            raise LookupError(f"no invoice with id {invoice_id!r}") from None

    def register_payment(
        self, invoice_id: str, amount_cents: int, paid_at: datetime
    ) -> PaymentReceipt:
        """Book a payment against an invoice.

        The open amount drops by the payment and the invoice becomes paid when nothing is open.
        A payment on an invoice with nothing open, or above the open amount, raises ValueError;
        an unknown id raises LookupError; a naive `paid_at` raises ValueError.
        """
        invoice = self.get_invoice(invoice_id)
        cents_to_str(amount_cents)  # the one money rule: int cents, not bool, not negative
        if amount_cents == 0:
            raise ValueError("a payment must be above zero")
        if paid_at.tzinfo is None or paid_at.utcoffset() is None:
            raise ValueError("paid_at must be timezone-aware")
        if invoice.open_amount_cents == 0:
            raise ValueError(f"invoice {invoice_id!r} has nothing open")
        if amount_cents > invoice.open_amount_cents:
            raise ValueError(f"payment is above the open amount of invoice {invoice_id!r}")
        remaining = invoice.open_amount_cents - amount_cents
        self._invoices[invoice_id] = replace(
            invoice,
            open_amount_cents=remaining,
            state=_PAID_STATE if remaining == 0 else invoice.state,
        )
        self._payments += 1
        return PaymentReceipt(
            id=f"fake-payment-{self._payments}",
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            paid_at=paid_at.astimezone(UTC),
        )

    def get_contact(self, contact_id: str) -> Contact:
        """Supported by this adapter."""
        self._load()
        try:
            return self._contacts[contact_id]
        except KeyError:
            raise LookupError(f"no contact with id {contact_id!r}") from None
