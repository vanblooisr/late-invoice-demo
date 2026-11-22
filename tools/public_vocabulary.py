"""Words and shapes that do not belong in the public tree: one list, imported by both tools.

tools/project_public_plan.py refuses to write the public plan when any of these survive its
rewrite, and tools/check_public_tree.py refuses the whole tree before an upload for the same
reasons. Keeping the list here means the two cannot drift apart. Each entry is (name, regex):
the name is what a hit prints, the regex is what it matches, case-insensitively unless the
pattern says otherwise.

Two groups:

- BANNED_VOCABULARY: words that describe how the software was made rather than what it does
  (the private workspace's roles, records, ids and process names), and the residues a mechanical
  rewrite can leave behind. An optional extra list, read from a file beside the repository, is
  added to it when that file exists.
- SECRET_SHAPES: strings that look like a credential. The tree checker applies these to every
  file; the projector's input never carries secrets, so it applies the vocabulary only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

BANNED_VOCABULARY: list[tuple[str, re.Pattern[str]]] = [
    (name, re.compile(pattern, re.I))
    for name, pattern in [
        ("operator", r"\boperator(?:'s|s)?\b"),
        ("operator_words", r"\boperator_words\b"),
        ("subagent", r"\bsub-?agents?\b"),
        ("helper agent", r"\bhelper agents?\b"),
        ("session", r"\bsessions?\b"),
        ("sess-", r"\bsess-\d{3}\b"),
        ("estate", r"\bestate\b"),
        ("private workspace placeholder", r"\bprivate workspace\b"),
        ("decision or finding id", r"\b[DF]-\{\d+\}\.\d+"),
        ("thread id", r"\bOT-\d{3}\b"),
        ("contract name", r"\b(?:annie|cascading)_v\d+\b|\bCONTRACT_\w+"),
        ("workspace name", r"\bannie\b"),
        ("reviewer", r"\b(?:code-)?reviewers?\b"),
        ("builder", r"\bbuilders?\b"),
        ("cascade", r"\bcascade\b"),
        ("plan version", r"\bthe v\d plan\b"),
        ("build-state wording", r"\bnot built yet\b"),
        ("Subagent step label", r"\bSubagent:"),
        ("quoted-words note", r"\boperator'?s? words?:"),
        ("weekday gate", r"\bMonday\b"),
        ("internal path", r"\b(?:Working|Archives)/(?:Projects|Reviewed|TOOLS)/"),
        ("doubled article residue", r"\b(?:the an|the a|a a|an an|a an)\s"),
        ("doubled word residue", r"\bbuild build\b"),
    ]
]

# An optional extra word list kept beside the repository, not in it: patterns that must stay out of
# the public tree and that a public file should not spell out. One rule per line, a name, a tab,
# then a regex; blank lines and lines starting with # are skipped. A missing file means no extra
# rules. Both tools print how many were loaded, so a clean result says what it covered.
LOCAL_VOCABULARY_ENV = "LID_LOCAL_VOCABULARY"
LOCAL_VOCABULARY_DEFAULT = Path(__file__).resolve().parents[2] / "local_vocabulary.txt"
TAB = chr(9)


def load_local_vocabulary() -> list[tuple[str, re.Pattern[str]]]:
    """Read the extra rules; a malformed line raises, so a broken list cannot pass as an empty one."""
    path = Path(os.environ.get(LOCAL_VOCABULARY_ENV) or LOCAL_VOCABULARY_DEFAULT)
    if not path.is_file():
        return []
    rules = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, tab, pattern = line.partition(TAB)
        if not tab or not name.strip() or not pattern.strip():
            raise ValueError(f"{path.name}:{number}: expected a name, a tab, then a regex")
        rules.append((name.strip(), re.compile(pattern.strip(), re.I)))
    return rules


LOCAL_VOCABULARY = load_local_vocabulary()
BANNED_VOCABULARY = BANNED_VOCABULARY + LOCAL_VOCABULARY

# ISO dates are a separate rule because some public files carry them by design (a documentation
# read date, an invoice due date in test data). The tools decide where they are allowed.
ISO_DATE = re.compile(r"(?<!\d)20\d\d-\d\d-\d\d(?!\d)")

SECRET_SHAPES: list[tuple[str, re.Pattern[str]]] = [
    ("mollie key with a value", re.compile(r"\b(?:live|test|access)_[A-Za-z0-9]{20,}\b")),
    ("bearer or token header with a value", re.compile(r"\b(?:Bearer|Token)\s+[A-Za-z0-9._+/=\-]{20,}", re.I)),
    # The bot id is digits, the secret follows a colon; the URL form .../bot<id>:<secret>/ counts too.
    ("telegram bot token", re.compile(r"(?<!\d)\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----")),
    # A filled assignment of one of the project's variables, in shell, PowerShell, Python, YAML or
    # dotenv form. The names are the ones .env.example lists.
    ("env assignment with a value", re.compile(
        r"(?:^|[\s\"'\[(])(?:export\s+|\$env:)?(?:MONEYBIRD_TOKEN|MONEYBIRD_ADMINISTRATION_ID|"
        r"MOLLIE_TEST_KEY|TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|TELEGRAM_USER_ID)[\"'\]]?\s*[:=]\s*[\"']?[A-Za-z0-9._:\-]{8,}",
        re.M | re.I)),
    # A long run of letters and digits with no separator and no prefix: the shape of a Moneybird
    # personal token (common/log.py redacts the same shape at 24 characters). It needs both letters
    # and digits, so a long identifier or word is not a hit; underscores and hyphens break the run,
    # so snake_case names are not hits either. A run after a colon counts (a "sha:" or "key:" label);
    # a run inside a URL path does not, since paths carry long segments by nature.
    ("long token-like run", re.compile(
        r"(?<![A-Za-z0-9_/.-])(?=[A-Za-z0-9]*[0-9])(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{24,}(?![A-Za-z0-9_/.-])")),
]

# Test code assigns dummy values to the project's variable names on purpose; the env-assignment
# rule does not apply there (the long-run rule still does).
ENV_RULE_EXEMPT_PREFIXES = ("core/tests/",)
