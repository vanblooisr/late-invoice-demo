# late-invoice-demo

A small program that takes a late invoice from "overdue" to "paid and booked" with one human decision
in between. It reads the late invoices from Moneybird, asks for approval in Telegram, creates a Mollie
payment link, and books the payment back into Moneybird once it has landed.

**Status: stage 1 of five, in progress.** The package installs and the `lid` command answers.
`lid fetch` runs on the Fake adapter: it records one row per late invoice, and a second run adds
none. The Moneybird adapter is written and passes the same contract test as the Fake, but it has not
run against a sandbox yet. The other four stage bodies are stubs that report "not implemented".

The tests are written before the code, and they are not in this repository yet. A stage gets one
complete test file here when it is finished; stage 1 is not finished, so there is none. What was
tested, what failed first and what was fixed is in `archives/`, in the logs and reports of every
build round, published whole. The seven vendor API facts the code depends on are checked against the
official documentation in `API-NOTES.md`. Everything below describes the finished demo; the stage
table says when each stage counts as done.

## The demo is four steps, and the fourth is the point

| # | What you see | What happens underneath |
|---|--------------|-------------------------|
| 1 | A late invoice in Moneybird | The program fetches every invoice with state `late` and records one row per invoice |
| 2 | A Telegram message: number, amount, days late, **Goedkeuren** / **Afwijzen** | Two inline buttons; a tap is accepted only from your own chat and your own user |
| 3 | After Goedkeuren: a payment link, opened and "paid" in the browser | A Mollie payment link in test mode, for exactly the open amount of the invoice |
| 4 | The invoice shows **paid** in Moneybird; Telegram says *Betaald* | The program polls the link until it is paid, confirms the open amount and the invoice state, and books the payment |

Turning an invoice into a payment link is step 3, and many tools stop there. Step 4 is the write-back:
the payment is booked against the right invoice, once, and only after the amount and the invoice
state have been checked. That step is where the errors live, so that step is what this demo is
built around.

## Five stages, each a program on its own

The demo is a ladder of five small programs, not one script. Each stage runs by itself, has its own
tests, and shows one thing. The fifth stage is the composed demo, and it falls out of the first four.

| Stage | Module · command | Done when |
|------|------------------|-----------|
| 1 | `fetch` · `lid fetch` | Prints the late invoices; running it twice adds no rows |
| 2 | `approve` · `lid approve` | A tap changes the status; a tap from a foreign chat is ignored; a second run sends no duplicate message |
| 3 | `link` · `lid link` | Approve yields a test link with the right amount; a paid invoice yields none; a second approve yields no second link |
| 4 | `writeback` · `lid check` | After the test payment the invoice is paid in Moneybird; running twice books once; an invoice paid some other way is reported, never booked again |
| 5 | `demo` · `lid demo` | The whole flow, three clean runs in a row, no secrets anywhere in the repo |

The stages grow in difficulty: read, then message, then write to one external system, then write to
two and keep them consistent. Every stage also runs as `python -m late_invoice_demo.<module>`.

## The rules the code keeps

Three rules sit above everything here: **safety and security** (nothing moves unless it is safe to
move), **transparency and traceability** (what happened must be readable from the record alone), and
**efficiency and design** (small parts that run alone, one way to do each thing). The eight rules
below are instances of those three. Each one is pinned by tests that exist before the code does;
the reports in `archives/` record which tests were watched failing before they passed, and which
were not.

1. **Secrets never enter the repo.** `.gitignore` before code, `.env.example` committed, test keys
   only, a secret scan before every upload, and a logger that never prints a token or a key.
2. **A payment is booked once.** One row per invoice. Before booking, a run claims the row with a
   single compare-and-set update from `link_created` to `booking`, so two runs cannot both book. A
   booking that was interrupted is reported as `booking_unconfirmed` and never repeated by the
   program.
3. **Nothing is booked blind.** Before a payment is registered, the invoice is re-read and must still
   be open, and the paid amount must equal the invoice's open amount to the cent. A customer who paid some
   other way in the meantime is reported, not booked twice.
4. **The code fails closed.** On any error, timeout, or value it does not recognise, a row stays as it
   was and the run says so. A failed connection is retried three times with a growing wait, and a
   rate-limit answer waits as long as the server asks; then the step cancels and reports it.
5. **Money is never a float.** Amounts are integer cents, formatted in one place. A float is rejected.
6. **Fake data only.** No real names, e-mail addresses, or amounts of existing companies.
7. **Anything not in the four steps is out of the demo.**
8. **Every step names its threats before it is built.** What can leak, what can go wrong with money,
   who can trigger what, and the guard for each. A step without that line does not start.

## The stages reach the books through one four-verb port

No stage calls Moneybird directly. Each talks to a *port*: an interface in `common/ports.py` that
says what a bookkeeping system must be able to do for this demo.

- list the late invoices
- read one invoice
- register a payment
- read a contact (optional)

Behind the port sit *adapters*. One is Moneybird. The other is a Fake: an in-memory adapter fed from
one small sample file that ships inside the package, with six invented invoices and three invented
contacts. The tests run against the Fake, which is what lets every stage be written and tested
before a single API key exists. Both adapters pass the same contract test, and an adapter for
another bookkeeping package would have to pass it too; that is the whole requirement, and the stages
would not change.

The port is four verbs on purpose. It is sized to this demo, not to bookkeeping in general.

## Install and run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.lock   # the exact pins
pip install -e . --no-deps         # the package itself
Copy-Item .env.example .env        # then fill it in locally
lid fetch                          # uses the fake adapter, no keys needed
lid fetch --adapter moneybird      # runs against your Moneybird sandbox
```

`.env` is never committed; `.env.example` lists the six variables with empty values.
`requirements.lock` pins every dependency to an exact version, runtime and development alike, so a
later install runs the same code; `pyproject.toml` keeps only the floors. There is nothing for
`pytest` to run here until the first stage is finished and its test file lands in `core/tests/`.

## What you need

| Part | What | Cost |
|------|------|------|
| Moneybird | A user account, a **sandbox** administration, a personal API token | Free |
| Mollie | An account with a **test** API key (starts with `test_`); test keys cannot move real money | Free in test mode |
| Telegram | A bot from @BotFather and your own chat id | Free |
| Python | 3.14, the version the code is written and tested on | Free |

The tests and the Fake adapter need none of these. Sandbox invoices carry a Moneybird watermark.

## Where things live

| Folder | Holds |
|--------|-------|
| `core/` | The software: one installable package, `late_invoice_demo`, with one module per stage, `common/` for shared parts, `adapters/` for the bookkeeping adapters and the Fake's sample data; `core/tests/` receives one complete test file per finished stage |
| `working/` | The public copy of the build plan and the project bulletin |
| `archives/` | The logs and reports of every build round, whole and as they were written, never edited after |
| `tools/` | The checks and generators for this repository: the plan generator, the archive publisher, the pre-upload check, the shared word list |

Shared code lives in `late_invoice_demo/common/`: the SQLite `actions` table, configuration from
`.env`, the port, and one amount formatter so Mollie and Moneybird never disagree about `"121.00"`.

Beside the folders sit `API-NOTES.md`, `.pre-commit-config.yaml` (the commit checks: a pinned secret
scanner with its `.secrets.baseline`, and `tools/check_public_tree.py`), `.env.example`,
`requirements.lock` and `pyproject.toml`.

## The record is published whole

`archives/` holds the log of every build round and the reports written along the way. They are
copied in as they were filed: the decisions and who made them, the findings, what was built, what
the reviews caught, what was left undone. Nothing is rewritten for the reader. One thing is blanked
on the way in: the value of a secret. `tools/publish_archives.py` does the copying; where a line
holds a key, a token or a filled credential it writes `[REDACTED]` in place of the value and leaves
the rest of the line as it was. A file with no secret in it is copied byte for byte. The build plan in
`working/` is the opposite case, a generated copy that keeps only the product; the logs are the
place to see how the work went.

Two checks run before every upload, and both cover `archives/` for secrets:

- `tools/check_public_tree.py` scans every tracked file for credential shapes. Outside `archives/`
  it also refuses words and dates that belong to the making of the code and not to the code; inside
  `archives/` those are the content, so only the secret rule applies there.
- A pinned secret scanner compares the tree with `.secrets.baseline`, the list of findings that were
  read and accepted as not secret: a pinned commit hash, two documentation lines about URLs with a
  password in them, and two report lines that name key names without a value.

**The baseline was generated on Windows, and its file names use backslashes.** On Windows the
scanner matches them. On Linux or macOS the same entries may not match, and the scanner will then
report those five findings again. Regenerate the baseline there with
`detect-secrets scan --baseline .secrets.baseline`, and read every entry it adds before you commit it.

## Fake data only, and a fixed scope

Every message in this demo passes through Telegram, and every amount through Mollie. On a sandbox
with invented customers that is harmless. On real invoices it is a different question: who may see
invoice data, under what agreement, and what happens when a wrong booking is a real correction. The
plan names that question and leaves it open. The demo does not answer it.

Not in this demo: dashboard, login, multiple users, OAuth, webhooks, a scheduler, real e-mail to
debtors, other bookkeeping packages, legal paperwork.

## Read more

- `working/late-invoice-demo-bulletin.html` — the project bulletin: the demo, the ladder, the state
  machine, the rules and the named risks, as a graphic. A single file, no dependencies, opens in a
  browser.
- `working/BUILDPLAN_late-invoice-demo_v1.yaml` — the public copy of the build plan: three phases,
  eleven steps, and a named risk beside every step. It is generated by
  `tools/project_public_plan.py`, and the next generation overwrites it, so it is not the place to
  edit.
- `archives/` — the log and the reports of every build round, whole. Start with the newest log; each
  one names what it built on.
- `archives/zero-point_test-baseline.md` — the whole test suite run before any stage body existed,
  every outcome listed with its reason.
- `API-NOTES.md` — the seven points checked against the official Mollie and Moneybird documentation
  before anything is built on them, with the URL and the date each was read.
- `tools/check_public_tree.py` — the check that runs before every upload over the files git tracks:
  credential shapes, the words listed in `tools/public_vocabulary.py`, and dates outside the files
  allowed to carry them. A file it cannot read counts as a hit, not as clean. In `archives/` only
  the credential rule applies. An optional extra word list can sit beside the repository; the check
  prints how many extra rules it loaded.

## Licence

MIT. See `LICENSE`.
