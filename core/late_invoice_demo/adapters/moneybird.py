"""The Moneybird adapter: implements BookkeepingPort against the Moneybird API."""

import logging
import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

import httpx

from ..common.entry import UnsupportedVerb
from ..common.money import MoneyError, cents_to_str, str_to_cents
from ..common.ports import (
    Contact,
    Invoice,
    PaymentOutcomeUnknown,
    PaymentReceipt,
    PaymentReplyUnusable,
)
from ..common.retry import retry

__all__ = [
    "CURRENCY_PATTERN",
    "DATE_PATTERN",
    "ID_PATTERN",
    "INVOICE_STATES",
    "MONEYBIRD_API",
    "MoneybirdAdapter",
]

MONEYBIRD_API = "https://moneybird.com/api/v2"

log = logging.getLogger(__name__)

# The invoice states API-NOTES.md (h) lists, less the filter-only value "all". A state outside
# this set is an unrecognised shape. These field rules are public because the local fake adapter
# applies the same ones to its own fixtures, so the two adapters accept the same shapes.
INVOICE_STATES = frozenset(
    {"draft", "open", "scheduled", "pending_payment", "late", "reminded", "paid", "uncollectible"}
)
ID_PATTERN = re.compile(r"[0-9]+")
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
CURRENCY_PATTERN = re.compile(r"[A-Z]{3}")


def _text(raw: Any, key: str, what: str) -> str:
    """The non-empty string at `key` of a vendor object, or RuntimeError naming the field."""
    value = raw.get(key) if isinstance(raw, dict) else None
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"moneybird: {what} has no usable {key!r}")
    return value


def _name_part(raw: dict, key: str, what: str) -> str:
    """A name part: a string that may be empty (a person has no company name, a company no first name)."""
    value = raw.get(key)
    if not isinstance(value, str):
        raise RuntimeError(f"moneybird: {what} has no usable {key!r}")
    return value.strip()


def _contact_name(raw: Any, what: str) -> str:
    """The company name, else first and last name joined; RuntimeError when both are empty."""
    if not isinstance(raw, dict):
        raise RuntimeError(f"moneybird: {what} has no contact object")
    company = _name_part(raw, "company_name", what)
    first = _name_part(raw, "firstname", what)
    last = _name_part(raw, "lastname", what)
    name = company or " ".join(part for part in (first, last) if part)
    if not name:
        raise RuntimeError(f"moneybird: {what} has a contact with no name")
    return name


def _amount(raw: dict, key: str, what: str) -> int:
    try:
        return str_to_cents(_text(raw, key, what))
    except MoneyError:
        raise RuntimeError(f"moneybird: {what} has an amount in an unrecognised shape ({key})") from None


def _invoice_from(raw: Any) -> Invoice:
    """Validate one vendor sales-invoice object and map it; any shape the notes do not cover raises."""
    if not isinstance(raw, dict):
        raise RuntimeError("moneybird: an invoice entry is not an object")
    what = "an invoice"
    invoice_id = _text(raw, "id", what)
    if ID_PATTERN.fullmatch(invoice_id) is None:
        raise RuntimeError("moneybird: an invoice id is not a string of digits")
    what = f"invoice {invoice_id}"
    state = _text(raw, "state", what)
    if state not in INVOICE_STATES:
        raise RuntimeError(f"moneybird: {what} has an unrecognised state {state!r}")
    due = _text(raw, "due_date", what)
    if DATE_PATTERN.fullmatch(due) is None:
        raise RuntimeError(f"moneybird: {what} has a due_date in an unrecognised shape")
    try:
        due_date = date.fromisoformat(due)
    except ValueError:
        raise RuntimeError(f"moneybird: {what} has a due_date that is not a calendar date") from None
    currency = _text(raw, "currency", what)
    if CURRENCY_PATTERN.fullmatch(currency) is None:
        raise RuntimeError(f"moneybird: {what} has a currency in an unrecognised shape")
    total = _amount(raw, "total_price_incl_tax", what)
    unpaid = _amount(raw, "total_unpaid", what)
    if unpaid > total:
        raise RuntimeError(f"moneybird: {what} has more unpaid than its total")
    return Invoice(
        id=invoice_id,
        invoice_number=_text(raw, "invoice_id", what),
        contact_id=_text(raw, "contact_id", what),
        contact_name=_contact_name(raw.get("contact"), what),
        amount_cents=total,
        open_amount_cents=unpaid,
        currency=currency,
        due_date=due_date,
        state=state,
    )


class MoneybirdAdapter:
    """Implements BookkeepingPort for one Moneybird administration.

    One administration per instance, addressed by id in every URL; the id must be ASCII digits.
    The token lives in exactly one place: the default headers of the adapter's httpx client
    (an Authorization header), so it also sits on every request object that client builds. The
    adapter stores it nowhere else; it never logs it, never puts it in a URL, repr or message of
    its own, and never chains an httpx exception from a payment request. The client lives for the
    adapter's lifetime and is built from `transport` when given, so tests answer requests without
    a network.

    Status handling (fail closed): on a read, 200 passes, 429 goes to the shared retry policy
    (see below), and every other status raises RuntimeError as an unexpected status. 404 and 422
    get no meaning of their own, because API-NOTES.md lists what they mean as open questions.
    A read that gives up (transport errors or 429 past the retries) raises a RuntimeError that
    names only the httpx error class or the status, with no cause or context: the httpx request
    object carries the Authorization header. Amount strings from the vendor are parsed by
    common/money.py; a value with another number of decimals is unrecognised.

    Reads (list, get invoice) run inside the shared retry policy: transport errors and 429 are
    retried. register_payment is sent exactly once, whatever happens, because a second POST could
    book the payment twice. Its failures are told apart by type, not by message: a transport
    error or an unexpected status raises PaymentOutcomeUnknown (the payment may or may not
    exist); a 201 whose reply is unusable raises PaymentReplyUnusable (the payment exists).

    Each vendor object is validated before it becomes an Invoice: a missing field, a state
    outside the documented set, an id that is not digits, a due_date that is not YYYY-MM-DD, a
    currency that is not three capitals, an amount that is not two decimals or more unpaid than
    the total raises RuntimeError. get_contact is not supported: the notes do not cover the
    contacts endpoint, so it raises UnsupportedVerb. Ids handed in by callers must be ASCII
    digits, else ValueError before any request.
    """

    def __init__(
        self,
        token: str,
        administration_id: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not isinstance(administration_id, str) or ID_PATTERN.fullmatch(administration_id) is None:
            raise ValueError("administration_id must be all ASCII digits")
        if not isinstance(token, str) or not token:
            raise ValueError("token must be a non-empty string")
        self.administration_id = administration_id
        self._transport = transport
        self.timeout = timeout
        self._base = f"{MONEYBIRD_API}/{administration_id}"
        self._client = httpx.Client(
            transport=transport,
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )

    def __repr__(self) -> str:
        return f"MoneybirdAdapter(administration_id={self.administration_id!r})"

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    # --- transport ------------------------------------------------------------------------
    @staticmethod
    def _invoice_segment(value: str) -> str:
        """One URL path segment from an invoice id: ASCII digits only, else ValueError."""
        if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
            raise ValueError("invoice_id must be a string of ASCII digits")
        return quote(value, safe="")

    @staticmethod
    def _check_status(response: httpx.Response) -> None:
        """Map a reply status on a read; only 200 passes.

        429 becomes an HTTPStatusError so the retry policy can read Retry-After. Anything else,
        404 and 422 included, is an unexpected status: the notes do not say what either means.
        """
        status = response.status_code
        if status == 429:
            response.raise_for_status()  # HTTPStatusError: the retry policy reads Retry-After
        if status != 200:
            raise RuntimeError(f"moneybird: unrecognised reply status {status}")

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET `path` under the administration inside the retry policy; return the parsed JSON."""

        def once() -> Any:
            response = self._client.get(f"{self._base}/{path}", params=params)
            log.debug("moneybird GET %s -> %s", path, response.status_code)
            self._check_status(response)
            try:
                return response.json()
            except ValueError:
                raise RuntimeError("moneybird: the reply is not JSON") from None

        failure: str | None = None
        try:
            return retry(once)
        except httpx.HTTPStatusError as exc:
            failure = f"rate limited (HTTP {exc.response.status_code}), not retried further"
        except httpx.HTTPError as exc:
            # The request object on the httpx exception carries the Authorization header, so
            # only the class name leaves this block; the raise below sits outside it so the
            # exception is not kept as implicit context either. The retry policy itself has
            # already seen the original httpx error on every attempt.
            failure = f"the request failed ({type(exc).__name__}) after the retries"
        raise RuntimeError(f"moneybird: {failure}") from None

    # --- the four verbs ---------------------------------------------------------------------
    def list_late_invoices(self) -> list[Invoice]:
        """Return invoices the bookkeeping system itself reports as late (its own late state), not a due-date computed here.

        Reads one reply of `sales_invoices.json?filter=state:late` and maps every entry in it. Whether
        the vendor paginates this list, and how a cut-off list would show, is an open question in
        API-NOTES.md; this method has no page size and no guard against a partial list.
        """
        body = self._get_json("sales_invoices.json", {"filter": "state:late"})
        if not isinstance(body, list):
            raise RuntimeError("moneybird: the invoice list is not a JSON array")
        return [_invoice_from(raw) for raw in body]

    def get_invoice(self, invoice_id: str) -> Invoice:
        """Return one invoice by id (ASCII digits; anything else raises ValueError before a request)."""
        segment = self._invoice_segment(invoice_id)
        invoice = _invoice_from(self._get_json(f"sales_invoices/{segment}.json"))
        if invoice.id != invoice_id:
            raise RuntimeError("moneybird: the reply is for a different invoice than asked")
        return invoice

    def register_payment(
        self, invoice_id: str, amount_cents: int, paid_at: datetime
    ) -> PaymentReceipt:
        """Book a payment against an invoice.

        Sends payment_date and price only. payment_date is the UTC calendar date of `paid_at`
        (half past midnight at +02:00 on New Year's Day sends the last day of the old year); which timezone the vendor means by
        that date is an open question in API-NOTES.md. The amount is sent as given: this adapter
        does not compare it with the open amount, the vendor decides.

        Sent exactly once. A non-digit invoice id, a payment of 0, a non-cents amount or a naive
        `paid_at` raises ValueError (MoneyError for the amount type) before any request. A
        transport error or any status other than 201 raises PaymentOutcomeUnknown; a 201 with an
        unusable reply raises PaymentReplyUnusable. The receipt carries the id the vendor gave
        the payment, the amount and `paid_at` (UTC) as sent.
        """
        segment = self._invoice_segment(invoice_id)
        price = cents_to_str(amount_cents)
        if amount_cents == 0:
            raise ValueError("a payment must be above zero")
        if paid_at.tzinfo is None or paid_at.utcoffset() is None:
            raise ValueError("paid_at must be timezone-aware")
        paid_utc = paid_at.astimezone(UTC)
        body = {"payment": {"payment_date": paid_utc.date().isoformat(), "price": price}}
        failure: str | None = None
        try:
            response = self._client.post(
                f"{self._base}/sales_invoices/{segment}/payments.json", json=body
            )
        except httpx.HTTPError as exc:
            # The request object on the httpx exception carries the Authorization header, so
            # only the class name leaves this block; the raise below sits outside it so the
            # exception is not even kept as implicit context.
            failure = type(exc).__name__
        if failure is not None:
            raise PaymentOutcomeUnknown(
                f"moneybird: the payment request failed ({failure}); "
                "the payment may or may not be registered"
            ) from None
        log.debug("moneybird POST payment for invoice %s -> %s", invoice_id, response.status_code)
        if response.status_code != 201:
            raise PaymentOutcomeUnknown(
                f"moneybird: unexpected reply status {response.status_code} to a payment; "
                "the payment may or may not be registered"
            )
        try:
            payment_id = _text(response.json(), "id", "the payment reply")
        except ValueError:
            raise PaymentReplyUnusable(
                "moneybird: the payment reply is not JSON; the payment is registered"
            ) from None
        except RuntimeError:
            raise PaymentReplyUnusable(
                "moneybird: the payment reply has no usable id; the payment is registered"
            ) from None
        return PaymentReceipt(
            id=payment_id, invoice_id=invoice_id, amount_cents=amount_cents, paid_at=paid_utc
        )

    def get_contact(self, contact_id: str) -> Contact:
        """Not supported: API-NOTES.md does not cover the contacts endpoint, so this raises UnsupportedVerb."""
        # A rule, not a gap to fill later: the adapter does not call the contacts endpoint because
        # the notes do not describe it.
        raise UnsupportedVerb(
            "moneybird: get_contact is not supported (the adapter does not call the contacts endpoint)"
        )
