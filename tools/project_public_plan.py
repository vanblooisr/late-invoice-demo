#!/usr/bin/env python3
"""Project the live build plan into its public form.

Reads the plan file (one YAML document, or several), keeps the top-level
sections named as public, drops the governance keys by name, refuses to write
when it meets a top-level key it does not know, removes quoted-word
fields and the plan's own bookkeeping keys, rewrites internal references, dates
and the words that describe how the plan was made rather than what the software
does, scans the result for banned text, and writes the public copy only when
the scan is clean.

Usage:
    project_public_plan.py --source SRC --out OUT
    project_public_plan.py --out OUT --check-only

Requires Python 3.14 and PyYAML.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from public_vocabulary import BANNED_VOCABULARY, ISO_DATE as ISO_DATE_RULE, LOCAL_VOCABULARY  # noqa: E402

# The keys that make up the governance section. They are dropped by name wherever they occur, so
# the source may be one document or several: the rule does not rest on where a separator sits.
DROP_KEYS = ("decision_ledger", "decision_trail", "version_history")
# The only top-level keys the public copy may carry. A top-level key that is neither here, nor in
# DROP_KEYS, nor in REMOVE_KEYS stops the run before anything is written: a new section is public
# only once it is named here.
PUBLIC_TOP_KEYS = frozenset(
    {
        "meta",
        "purpose_and_design_goals",
        "system_model",
        "scope_boundaries",
        "phase_definitions",
        "interdependency_map",
        "execution_state",
        "quality_gates",
        "open_threads",
    }
)
# Keys removed wherever they occur: quoted words, the plan's own bookkeeping about how it was
# made, pointers into records the public reader cannot open, and the way the work is organised.
REMOVE_KEYS = frozenset(
    {
        "operator_words",
        "entry_note",
        "authority",
        "stateskill_version",
        "standard_version",
        "bot_version",
        "sessions",
        "placement",
        "companion",
        "kb_basis",
        "kb_refs",
        "execution_model",
        "decisions",
        "approval",
    }
)

REF_PAREN = re.compile(
    r"\s*\((?:D|F)-\{\d+\}\.\d+(?:[/,\s]*(?:\.|(?:D|F)-\{\d+\}\.)?\d+)*[^)]*\)"
)
REF_BARE = re.compile(r"\b(?:D|F)-\{\d+\}\.\d+(?:\s*/\s*\.?\d+)*")
ISO_DATE = ISO_DATE_RULE
# A date with the word in front of it that gives it its role; the pair is rewritten together so no
# preposition is left dangling and no future date reads as a past one.
DATE_REWRITES = [
    (re.compile(r"\b(?:Verified|verified|approved|Approved)\s+" + ISO_DATE_RULE.pattern), lambda m: m.group(0).split()[0]),
    (re.compile(r"\(sunset\s+" + ISO_DATE_RULE.pattern + r"\)"), "(with a sunset date)"),
    (re.compile(r"\bexpected\s+" + ISO_DATE_RULE.pattern), "expected later"),
    (re.compile(r"\b(?:on|at|by|until|before|after)\s+" + ISO_DATE_RULE.pattern), "later"),
]
WEEKDAY = re.compile(r"(?:\b(?:the|a)\s+)?\bMonday\b", re.I)
STEP_LABEL = re.compile(r"Subagent:", re.I)
QUOTE_PAREN = re.compile(r"\s*\((?:the\s+)?operator'?s?\s+words?:[^)]*\)", re.I)
INTERNAL_PATH = re.compile(
    r"(?:(?i:Working/(?:Projects|Reviewed|TOOLS))|Archives(?:/Projects)?)/\S+"
)
# Thread ids: a parenthesised pointer is dropped; a bare id becomes a Q-nnn that resolves to the
# public open_threads list (ids there are rewritten the same way). THREAD_PAREN runs before THREAD_ID.
THREAD_PAREN = re.compile(r"\s*\((?:see\s+open_threads\s+)?OT-\d{3}[^)]*\)")
THREAD_ID = re.compile(r"\bOT-(\d{3})\b")
# Words that describe how the plan was made, not what the software does.
# ORDER MATTERS: longer and more specific patterns first. Each rule that puts in a noun phrase
# with its own article first eats any article already in front of the match, so "the session-002
# REPORT" becomes "the earlier build round's record", never "the an earlier ...". The scan at the
# end refuses doubled articles as a guard (public_vocabulary BANNED_VOCABULARY).
WORD_REWRITES = [
    (re.compile(r"(?:\b(?:the|a|an)\s+)?\b(?:session|sess)[- ]\d{3}\s+review\b", re.I), "an earlier review"),
    (re.compile(r"\bOpened (?:session|sess)[- ]\d{3}\b"), "Opened"),
    (re.compile(r"\bPost-close (?:session|sess)[- ]\d{3}\b"), "After a later close"),
    (re.compile(r"(?:\b(?:the|a|an)\s+)?\b(?:session|sess)[- ]\d{3}\s+(?:REPORT|LOG|close)\b", re.I), "an earlier build round's record"),
    (re.compile(r"(?:\b(?:the|a|an)\s+)?\b(?:session|sess)[- ]\d{3}\b", re.I), "an earlier build round"),
    (re.compile(r"\bbuild sessions\b", re.I), "build rounds"),
    (re.compile(r"\bbuild session\b", re.I), "build round"),
    (re.compile(r"\bSessions\b"), "Build rounds"),
    (re.compile(r"\bsessions\b"), "build rounds"),
    (re.compile(r"\bSession\b"), "Build round"),
    (re.compile(r"\bsession\b"), "build round"),
    (re.compile(r"\bOperator-only\b"), "Owner-only"),
    (re.compile(r"\boperator-(side|scheduled)\b", re.I), r"owner-\1"),
    (re.compile(r"\bOperator\b"), "Owner"),
    (re.compile(r"\boperator\b"), "owner"),
    (re.compile(r"\bsub-?agents\b", re.I), "helpers"),
    (re.compile(r"(?:\b(?:the|a|an)\s+)?\bsub-?agent\b", re.I), "a helper"),
    (re.compile(r"\bcode-reviewers?\b", re.I), "review"),
    (re.compile(r"\breviewers?\b", re.I), "review"),
    (re.compile(r"\bbuilders?\b", re.I), "whoever writes the code"),
    (re.compile(r"\bcascade executes\b", re.I), "the build runs"),
    (re.compile(r"\bcode-build flow\b", re.I), "build flow"),
    (re.compile(r"\bthe journalism skill\b", re.I), "a writing pass"),
    (re.compile(r"\bhook-blocked for the model\b", re.I), "blocked by tooling"),
    (re.compile(r"\bthe envelope records\b", re.I), "the review records"),
    (re.compile(r"\bthe envelope\b", re.I), "the review"),
    (re.compile(r"\s*\b(?:Estate|home folder) precedent: .*?\)\.?"), ""),
    (re.compile(r"\bRead by four sonnet gatherers through the fetch tool and VERIFIED in the main thread against", re.I), "Read through a fetch tool and verified against"),
    (re.compile(r"\bthe v\d plan\b", re.I), "the plan"),
    (re.compile(r"\bthe estate's\b", re.I), "this plan's home folder's"),
    (re.compile(r"\bthe estate\b", re.I), "this plan's home folder"),
    (re.compile(r"\bestate\b", re.I), "home folder"),
]
# Sentences whose only content is a pointer to a private path carry nothing for the public reader:
# the whole clause goes, not the path alone.
PRIVATE_PATH_CLAUSE = re.compile(
    r"\s*(?:[—-]\s+(?:(?:see|at|in|under|lives at|live at|is at|are in)\s+)?|\s(?:see|at|in|under|lives at|live at|is at|are in)\s+)(?:(?i:Working/(?:Projects|Reviewed|TOOLS))|Archives(?:/Projects)?)/\S+"
)
# Threads that are about the private workspace's own bookkeeping, not about the product.
REMOVE_THREADS = frozenset({"OT-001", "OT-006", "OT-009"})
SENTENCE_START = re.compile(r"(^|[.:!?]\s+)an earlier (build round|review|date)")

# The shared list, plus two rules that only make sense for the plan text: a date anywhere in it,
# and the private archive folder by exact case (the public repo has its own lower-case archives/).
BANNED = list(BANNED_VOCABULARY) + [
    ("iso-date", ISO_DATE),
    ("Archives/", re.compile(r"Archives/")),
]


class Counts:
    def __init__(self) -> None:
        self.keys_removed = 0
        self.refs = 0
        self.dates = 0
        self.paths = 0
        self.quotes = 0
        self.words = 0


def rewrite_string(text: str, counts: Counts) -> str:
    # ORDER MATTERS. Quoted-word notes go first (a later rule would turn "operator's words:" into
    # "owner's words:" and the note would escape removal). Parenthesised references go before bare
    # ones. A clause that only points at a private path goes before the bare path rewrite.
    def _path(match: re.Match) -> str:
        counts.paths += 1
        tail = re.search(r"[.,;:)\]]*$", match.group(0)).group(0)
        return "a private folder" + tail

    text, n = QUOTE_PAREN.subn("", text)
    counts.quotes += n
    counts.words += n
    # The repository's own folder is the one private path the public reader can name.
    text, n = re.subn(r"Working/Projects/late-invoice-demo/repo/?", "the repository folder", text)
    counts.paths += n
    text, n = PRIVATE_PATH_CLAUSE.subn("", text)
    counts.paths += n
    text = INTERNAL_PATH.sub(_path, text)
    text, n = REF_PAREN.subn("", text)
    counts.refs += n
    # A bare decision reference: the clause it anchors stays, the pointer becomes a plain noun.
    text, n = REF_BARE.subn("a ruling", text)
    counts.refs += n
    for pattern, replacement in DATE_REWRITES:
        text, n = pattern.subn(replacement, text)
        counts.dates += n
    text, n = ISO_DATE.subn("an earlier date", text)
    counts.dates += n
    text, n = WEEKDAY.subn("a later weekday", text)
    counts.words += n
    text, n = STEP_LABEL.subn("Build step:", text)
    counts.words += n
    text, n = THREAD_PAREN.subn("", text)
    counts.words += n
    text, n = THREAD_ID.subn(r"Q-\1", text)
    counts.words += n
    for pattern, replacement in WORD_REWRITES:
        text, n = pattern.subn(replacement, text)
        counts.words += n
    text = SENTENCE_START.sub(lambda m: m.group(1) + "An earlier " + m.group(2), text)
    return text


def walk(node, counts: Counts):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            # A governance key is dropped at any depth, not only at the top of a document.
            if key in REMOVE_KEYS or key in DROP_KEYS:
                counts.keys_removed += 1
                continue
            out[key] = walk(value, counts)
        return out
    if isinstance(node, list):
        kept = [item for item in node if not (isinstance(item, dict) and item.get("id") in REMOVE_THREADS)]
        counts.keys_removed += len(node) - len(kept)
        return [walk(item, counts) for item in kept]
    if isinstance(node, str):
        return rewrite_string(node, counts)
    return node


def is_empty(doc) -> bool:
    """A document whose every value was removed carries nothing for the reader."""
    return doc is None or doc == {} or (isinstance(doc, dict) and all(v in ({}, None, "") for v in doc.values()))


def scan(text: str) -> list[tuple[int, str, str]]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in BANNED:
            if pattern.search(line):
                hits.append((lineno, name, line.strip()))
    return hits


def strings_of(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from strings_of(key)
            yield from strings_of(value)
    elif isinstance(node, list):
        for item in node:
            yield from strings_of(item)
    elif isinstance(node, str):
        yield node


def scan_values(docs: list) -> list[tuple[int, str, str]]:
    """Scan the unwrapped string values, flattened, so line wrapping cannot hide a hit.

    Each (rule, text) pair is reported once; the line number is 0 because a value has no line in
    the source document.
    """
    hits: list[tuple[int, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for value in strings_of(docs):
        flat = " ".join(value.split())
        for name, pattern in BANNED:
            if pattern.search(flat) and (name, flat) not in seen:
                seen.add((name, flat))
                hits.append((0, name, flat))
    return hits


def first_sentence(text: str) -> str:
    flat = " ".join(str(text).split())
    match = re.search(r"\.(?:\s|$)", flat)
    return flat[: match.end()].strip() if match else flat


def render(docs: list) -> str:
    purpose = ""
    for doc in docs:
        if isinstance(doc, dict) and "purpose_and_design_goals" in doc:
            purpose = first_sentence(doc["purpose_and_design_goals"].get("purpose", ""))
            break
    header = (
        "# PLAN: late-invoice-demo — public copy of the build plan\n"
        "# Generated by tools/project_public_plan.py from the plan's source copy, which is kept "
        "outside this repository; the governance section, decision references, dates, quoted words "
        "and words about how the plan was made are removed. Do not edit here: the next generation "
        "overwrites this file.\n"
        f"# Purpose: {purpose}\n"
    )
    parts = [
        yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=110) for d in docs
    ]
    return header + "---\n" + "---\n".join(parts)


def keys_of(node):
    """Every mapping key in the tree, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys_of(value)
    elif isinstance(node, list):
        for item in node:
            yield from keys_of(item)


def has_anchor_or_alias(text: str) -> bool:
    """True when the YAML text names a node once and uses it again elsewhere.

    An alias is resolved at load, so a value written under a governance key and reused in a public
    section would survive the removal of the key. A source with either token is not projected.
    """
    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            return True
    return False


def report_hits(hits) -> None:
    for lineno, name, line in hits:
        print(f"banned [{name}] line {lineno}: {line[:160]}", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Project the live plan into its public form.")
    ap.add_argument("--source", help="path of the live plan")
    ap.add_argument("--out", help="path of the public copy")
    ap.add_argument("--check-only", action="store_true",
                    help="scan an existing --out file and exit 0 (clean) or 1")
    args = ap.parse_args(argv)

    if args.check_only:
        if not args.out:
            ap.print_usage(sys.stderr)
            return 2
        text = Path(args.out).read_text(encoding="utf-8")
        # The same checks as generation: the rendered lines, the unwrapped values (a wrapped line
        # cannot hide a phrase), and the structure (no governance key, no unnamed section).
        public_docs = [d for d in yaml.safe_load_all(text) if d is not None]
        hits = scan(text) + scan_values(public_docs)
        report_hits(hits)
        structure = []
        for doc in public_docs:
            if not isinstance(doc, dict):
                structure.append("a document that is not a mapping")
                continue
            structure += [f"governance key {k}" for k in keys_of(doc) if k in DROP_KEYS]
            structure += [f"unnamed top-level key {k}" for k in doc if k not in PUBLIC_TOP_KEYS]
        for problem in structure:
            print(f"structure: {problem}", file=sys.stderr)
        print(f"check-only: banned hits {len(hits)}; structure problems {len(structure)}")
        return 1 if hits or structure else 0

    if not args.source or not args.out:
        ap.print_usage(sys.stderr)
        return 2

    source_text = Path(args.source).read_text(encoding="utf-8")
    if has_anchor_or_alias(source_text):
        print("refused: the source uses a YAML anchor or alias; nothing written", file=sys.stderr)
        return 1
    docs = [d for d in yaml.safe_load_all(source_text) if d is not None]

    counts = Counts()
    kept_raw, dropped, unknown = [], 0, []
    for doc in docs:
        if not isinstance(doc, dict):
            unknown.append("(a document that is not a mapping)")
            continue
        public = {}
        for key, value in doc.items():
            if key in DROP_KEYS:
                counts.keys_removed += 1
            elif key in PUBLIC_TOP_KEYS or key in REMOVE_KEYS:
                public[key] = value
            else:
                unknown.append(str(key))
        if public:
            kept_raw.append(public)
        else:
            dropped += 1
    if unknown:
        print(
            "refused: top-level key(s) not named as public or governance: "
            + ", ".join(sorted(unknown))
            + "; nothing written",
            file=sys.stderr,
        )
        return 1

    kept = []
    for d in kept_raw:
        rewritten = walk(d, counts)
        # A section left with nothing after the removals is not printed as an empty key.
        rewritten = {k: v for k, v in rewritten.items() if v not in ({}, None, "")}
        if is_empty(rewritten):
            dropped += 1
        else:
            kept.append(rewritten)
    text = render(kept)
    hits = scan(text) + scan_values(kept)
    if hits:
        report_hits(hits)
        print(f"refused: {len(hits)} banned hit(s); nothing written", file=sys.stderr)
        return 1

    Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    print(
        f"documents kept {len(kept)}, dropped {dropped}; "
        f"keys removed {counts.keys_removed}; "
        f"references rewritten {counts.refs}; dates rewritten {counts.dates}; "
        f"words rewritten {counts.words}; "
        f"internal paths rewritten {counts.paths}; "
        f"quoted-word notes removed {counts.quotes}; "
        f"banned hits 0; extra word-list rules loaded {len(LOCAL_VOCABULARY)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
