# API notes

What the code assumes about the two vendor APIs, read from their official documentation.
Every answer carries the URL it was read from and the read date. When a vendor changes a
page, the answer here is stale until it is re-read; the stages that depend on an answer
are named so the re-read can be targeted.

Method of reading: the documentation pages were fetched and the quoted phrases were
checked against the raw page text. Where a page is silent, the entry says "not stated"
rather than guessing. Items marked *inferred* follow from what the page says but are not
said by it.

Every section has the same shape: *Source* (the pages), *Read* (the date those pages were
read; re-reading one section changes only its own date), the answer as bullets with
"not stated" and *inferred* marked inline, and *Depends on this* (the stage or module that
rests on the answer). The letters (a) to (g) are the seven questions the build plan asks
before anything is built on the vendor APIs; (h) and (i) are supporting detail the adapter
and the polling wait need.

## Mollie

### (a) Which payment-link field signals paid, and what the paid amount field is

Source: https://docs.mollie.com/reference/get-payment-link and
https://docs.mollie.com/reference/get-payment-link-payments
Read: 2026-11-20

- Paid signal: `paidAt`, a string or null. Doc text: "The date and time the payment link
  became paid, in ISO 8601 format." It is the only paid indicator on the payment-link
  object; there is no `status` field and no boolean. *Inferred:* `null` means unpaid.
- Paid amount: **not on the payment-link object.** The object's `amount` is the requested
  amount ("The amount of the payment link"), not what was paid, and there is no
  `amountPaid` or similar field. The paid amount comes from the link's payments:
  `GET https://api.mollie.com/v2/payment-links/{paymentLinkId}/payments` returns
  `count` and `_embedded.payments`, "An array of payment objects." Each payment carries
  `amount` ({`currency`, `value`}), `status` and `paidAt`.
- Amount shape everywhere: an object with `currency` (ISO 4217) and `value` (a string).
  Doc text: "A string containing an exact monetary amount in the given currency."
  Examples use two decimals ("10.00", "1000.00"); an explicit two-decimal rule is **not
  stated** for EUR. The code sends and parses exactly two decimals (common/money.py);
  a reply with another number of decimals is treated as unrecognised and fails closed.
- Other fields on the object used by the code: `id` (prefix `pl_`), `_links.paymentLink.href`
  (the URL the customer opens), `expiresAt` (ISO 8601 string or null), `archived`
  (boolean), `reusable` (boolean or null, default false: "allowing only a single payment
  per link").
- Create request (https://docs.mollie.com/reference/create-payment-link): the only
  required field is `description` (max 255 characters). `amount` is optional (without it
  the customer enters an amount); `expiresAt` is an optional ISO 8601 string, and without
  it "the payment link will not expire automatically." `reusable` defaults to false.

Depends on this: stage 3 (link) for the create request; stage 4 (writeback) for `paidAt`
and the payments sub-resource. **Design consequence:** the amount check in the
double-payment guard needs a second request (the payments list), not just the link.

### (d) Whether Wero shows on the Mollie test pay page

Source: https://docs.mollie.com/docs/wero and https://docs.mollie.com/docs/testing
Read: 2026-11-20

- Wero exists as a method (`wero`), in beta: "Wero is available in Beta in Germany,
  Belgium, France & the Netherlands." Activation: "You can activate Wero via your Mollie
  Dashboard", subject to a merchant review.
- Test mode: the testing page says "In test mode, payment methods are activated
  immediately even when they show as pending" and describes a test checkout where the
  payment status is picked by hand. **Neither page mentions the other:** the Wero page
  says nothing about test mode and the testing page does not name Wero.
- Status: **not stated.** *Inferred:* an activated Wero shows on the test checkout like
  any other activated method, but the beta review may gate it. To be confirmed by
  opening a test link once a test key exists; nothing in the code depends on the answer.
- Per-link restriction exists: `allowedMethods` on create and update; "When this
  parameter is not provided or is an empty array, all enabled payment methods will be
  available."

Depends on this: the demo narrative only.

### (e) Whether Mollie accepts an Idempotency-Key header on payment-link creation

Source: https://docs.mollie.com/reference/api-idempotency
Read: 2026-11-20

- Header name: `Idempotency-Key`. "All POST endpoints accept idempotency keys." The page
  does not list endpoints by name; payment-link creation is a POST, so it qualifies
  (*inferred* from the general rule).
- Behaviour: a repeat with the same key and the same request returns the cached response
  with the header `Idempotent-Replayed: true`. The same key with a different endpoint or
  parameters answers `400 Bad Request`. A duplicate while the first is still processing
  answers `409 Conflict`.
- Retention: "Keys older than 1 hour will be removed from our cache." After that the same
  key is a new request. Keys are tied to the API credential used on the first request.
- Format: no length or character rule is stated; the page recommends UUID4.

Depends on this: stage 3 (link). **Design consequence:** the key protects the immediate
retry of a timed-out POST, within the hour. The durable guard against a second link is
the stored link id on the row: a row that already holds a link id is never POSTed again,
and a run that finds no link id but has a key still within the hour gets the same link
back. Past the hour the key is gone: a row whose POST was lost and that is retried later
than an hour can get a second link, so the stage compares the returned link's amount and
description with the row and reports a mismatch rather than storing it silently; the
retried request must also carry the same body (same expiry), since a reused key with a
different body answers 400.

### (g) Whether a payment link can be deactivated after creation

Source: https://docs.mollie.com/reference/update-payment-link and
https://docs.mollie.com/reference/delete-payment-link
Read: 2026-11-20

- Yes, two ways. Archive: `PATCH /v2/payment-links/{paymentLinkId}` with `"archived": true`;
  "Customers will not be able to complete payments on archived payment links." Delete:
  `DELETE /v2/payment-links/{paymentLinkId}`, allowed only for links "which have not been
  opened and no payments have been made yet"; answers 204, and 422 once a payment exists.
- The update endpoint can change `description`, `minimumAmount`, `archived`,
  `allowedMethods`, `lines`, `billingAddress`, `shippingAddress`. It cannot change
  `amount`, `expiresAt`, `reusable`, `redirectUrl` or `webhookUrl`.
- Not stated: what the customer sees on an archived link; whether `archived` can be set
  back to false; whether archiving a paid link is refused (the schema lists no condition,
  so *inferred* allowed).
- Scope for access tokens and OAuth: `payment-links.write` (an API key has every scope).

Depends on this: stage 4 (writeback) for the paid-elsewhere case: the code archives the
link; it does not try to delete it, since a link the customer has opened cannot be deleted.

### (i) Mollie rate limits

Source: https://docs.mollie.com/reference/rate-limiting
Read: 2026-11-21

- No fixed number is published. "Rate limits are scoped per merchant and calculated
  dynamically based on observed traffic patterns"; they "are measured in requests per
  second", with a burst allowance on top.
- Read and write are separate buckets: `GET`, `HEAD`, `OPTIONS` count as read; `POST`,
  `PUT`, `PATCH`, `DELETE` as write. All API keys of one merchant share the same bucket.
- Every response carries `RateLimit-Policy` (policy name, sustained rate `q` in requests
  per second, window `w`) and `RateLimit` (remaining `r`, seconds until full `t`). The
  page's example policy is `"get-v2-payments";q=20;w=3;mollie-burst=60`; that is an
  example, not a stated limit for this account.
- Over the limit: `429 Too Many Requests` with `Retry-After`, "integer seconds until your
  next request slot opens", present only on a 429. The page asks for retry and backoff
  logic and for slowing down when the remaining count runs low.
- Test mode: "may have lower limits than live environments".
- Not stated: the actual limit for a test key on the payment-links endpoints. It can be
  read from the `RateLimit-Policy` header of the first real response.

Depends on this: the polling wait in the demo stage and the retry policy
(common/retry.py); the poll interval is chosen from the header once a test key exists.

## Moneybird

### (b) Whether create-payment needs financial_account_id

Source: https://developer.moneybird.com/api/sales-invoices/ (the "Create a payment"
Read: 2026-11-20
operation and its request schema)

- Endpoint: `POST https://moneybird.com/api/v2/{administration_id}/sales_invoices/{sales_invoice_id}/payments.json`,
  scope `sales_invoices`, answers `201 Payment created` with the payment object.
- Body: `{"payment": {...}}`. Required: `payment_date` ("The date on which the payment was
  made.", a date string, `YYYY-MM-DD` in the response) and `price` ("The amount paid in the
  document's currency."). Optional: `price_base` (required only when the invoice currency
  differs from the administration's base currency), `financial_account_id`,
  `financial_mutation_id`, `transaction_identifier`, `manual_payment_action`,
  `ledger_account_id`, `invoice_id`.
- `financial_account_id` is **optional**: "Required for `private_payment` and
  `cash_payment` actions." Without a `manual_payment_action` it is not needed. The code
  sends `payment_date` and `price` only; it may add `transaction_identifier` with the Mollie
  payment id so the payment can be matched to a bank mutation later.
- Money format: "Both a decimal and a string '10,95' are accepted." The schema pattern is
  `^-?[0-9]+[,\.]?[0-9]*$`; the examples show `"363.0"`. The code sends the two-decimal
  string from common/money.py, which matches the pattern.
- The older `PATCH .../sales_invoices/{id}/register_payment.json` is marked deprecated with
  a sunset date of 2026-12-31; the code uses the POST.
- Delete: `DELETE .../sales_invoices/{sales_invoice_id}/payments/{id}.json`.

Depends on this: stage 4 (writeback), the Moneybird adapter's `register_payment`.

### (c) Moneybird throttling limits

Source: https://developer.moneybird.com/introduction (Throttling)
Read: 2026-11-20

- "requests to the API are throttled on a per ip-address basis. You can request the API
  150 times each 5 minutes, with a stricter limit of 50 requests per 5 minutes for all the
  /reports/ endpoints." The limit is per IP address, not per token or administration.
- Over the limit: `429 Too many requests`. Response headers on every reply:
  `RateLimit-RequestsRemaining`, `Retry-After`, `RateLimit-Remaining`, `RateLimit-Limit`,
  `RateLimit-Reset`. Best practice from the page: after a 429, wait until `Retry-After`.
- Demo scale: a full run is well under 20 requests, so the limit is not reachable; the
  retry policy retries a 429 and waits the seconds its `Retry-After` header names.

Depends on this: the Moneybird adapter and the retry policy (common/retry.py).

### (f) Whether a Moneybird personal token can be scoped

Source: https://developer.moneybird.com/authentication/
Read: 2026-11-20

- Scopes apply to personal tokens: "For a personal API token, you can use the checkboxes
  to select the scopes you need." The six scopes: `sales_invoices`, `documents`,
  `estimates`, `bank`, `time_entries`, `settings`. The token for this demo needs
  `sales_invoices` only (listing invoices and creating a payment both sit under it).
- No read-only variant is stated; scopes are not split into read and write.
- Per-administration limit: **not stated.** The page says a personal token "is similar to a
  password and gives access to your entire company account." The administration is chosen
  by the URL (`/{administration_id}/...`), so the code addresses exactly one id from the
  environment and never lists administrations.
- Expiry and revocation of personal tokens: not stated on the page (the "does not expire"
  line is about OAuth access tokens).
- Sandbox: "We offer special sandbox administrations to test your API integration" and
  "invoices have watermarks." No sandbox-only token is described.

Depends on this: the setup step (which scope box to tick) and the Moneybird adapter.

### (h) Sales-invoice fields the adapter maps (supporting detail for the port)

Source: https://developer.moneybird.com/api/sales-invoices/ (List all invoices, schema)
Read: 2026-11-20

- `GET .../sales_invoices.json?filter=state:late`. Filters are "key:value terms separated by
  commas"; "Any filter you pass replaces the defaults below entirely", so passing only
  `state:late` drops the default `period:this_year` and returns late invoices of every
  date, which is what the fetch stage wants. State values: `all`, `draft`, `open`,
  `scheduled`, `pending_payment`, `late`, `reminded`, `paid`, `uncollectible`.
- Fields the adapter reads: `id` (string of digits), `invoice_id` (the printed invoice
  number, null while draft), `state`, `contact_id`, `due_date` (date string),
  `total_price_incl_tax` and `total_unpaid` (strings), `currency`, and the nested
  `contact` with `company_name`, `firstname`, `lastname` (no single name field; a private
  person has an empty `company_name`, so the adapter falls back to first and last name).
- The decimal format of the vendor's amount strings is **not stated**; the examples on the
  create-payment page show one decimal ("363.0"). The adapter parses them with
  common/money.py's strict two-decimal grammar and treats any other shape as unrecognised
  (fail closed), so a one-decimal reply from the sandbox would show up as a reported
  refusal on the first live run, not as a wrong amount.

Depends on this: the Moneybird adapter's mapping of the list and get replies to Invoice.

## Open before the first live run — not read yet

Questions only; none of these is answered by the pages read above.

- Do the list endpoints paginate, and how does a cut-off list show? The adapter reads one
  reply and would not notice a partial list.
- The contacts endpoint: does it exist in the shape the port needs, which fields does it
  return, and which token scope does it sit under?
- What do 404 and 422 mean on the sales-invoice endpoints?
- Which timezone defines `payment_date`?
- Can the price or date in the 201 reply differ from what was sent?
