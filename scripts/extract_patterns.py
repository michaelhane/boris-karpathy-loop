#!/usr/bin/env python3
"""
extract_patterns.py — turn closed review findings into anti-pattern guide entries.

Reads `reviews/*.md` files with `status: closed` in their frontmatter, extracts
BLOCKER and CONCERN findings, and appends them as candidate anti-patterns to a
target guide.

Idempotent: skips findings whose title hash already appears in the target file.

Usage:
    python scripts/extract_patterns.py \\
        --reviews-dir reviews/ \\
        --target guides/anti-patterns.md

    python scripts/extract_patterns.py \\
        --reviews-dir reviews/ \\
        --target guides/anti-patterns.md \\
        --since 2026-01-01 \\
        --severities BLOCKER,CONCERN \\
        --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date, datetime
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
FINDING_HEADER_RE = re.compile(r"^### \[(BLOCKER|CONCERN|NIT)\]\s+(.+?)$", re.MULTILINE)
FIELD_RE = re.compile(r"^-\s+\*\*([^:]+):\*\*\s+(.+)$", re.MULTILINE)
HASH_TAG_RE = re.compile(r"<!--\s*pattern-hash:\s*([a-f0-9]{12})\s*-->")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Cheap YAML-ish parser. Only handles top-level key: value pairs."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def extract_findings(text: str, severities: set[str]) -> list[dict]:
    """Pull findings of the requested severities out of a review body."""
    findings: list[dict] = []
    sections = FINDING_HEADER_RE.split(text)
    # split returns: [pre, sev1, title1, body1, sev2, title2, body2, ...]
    for i in range(1, len(sections), 3):
        severity = sections[i]
        title = sections[i + 1].strip()
        body = sections[i + 2] if i + 2 < len(sections) else ""
        if severity not in severities:
            continue
        fields = dict(FIELD_RE.findall(body))
        findings.append(
            {
                "severity": severity,
                "title": title,
                "principle": fields.get("Principle", "?"),
                "where": fields.get("Where", ""),
                "why": fields.get("Why it matters", ""),
                "resolution": fields.get("Suggested resolution", ""),
            }
        )
    return findings


def pattern_hash(title: str) -> str:
    """Stable short hash of the finding title — used for idempotency."""
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:12]


def existing_hashes(target: Path) -> set[str]:
    if not target.exists():
        return set()
    return set(HASH_TAG_RE.findall(target.read_text(encoding="utf-8")))


def render_entry(finding: dict, source_review: str) -> str:
    h = pattern_hash(finding["title"])
    return (
        f"### {finding['title']}\n"
        f"<!-- pattern-hash: {h} -->\n\n"
        f"- **Severity:** {finding['severity']}\n"
        f"- **Principle:** {finding['principle']}\n"
        f"- **Why it doesn't work:** {finding['why']}\n"
        f"- **Direction:** {finding['resolution']}\n"
        f"- **Source:** [{source_review}](../reviews/{source_review})\n\n"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reviews-dir", type=Path, default=Path("reviews"))
    p.add_argument("--target", type=Path, default=Path("guides/anti-patterns.md"))
    p.add_argument("--since", type=str, default=None, help="Only consider reviews from this date onwards (YYYY-MM-DD).")
    p.add_argument("--severities", type=str, default="BLOCKER,CONCERN")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not args.reviews_dir.is_dir():
        print(f"reviews dir {args.reviews_dir} not found", file=sys.stderr)
        return 1

    severities = {s.strip().upper() for s in args.severities.split(",") if s.strip()}
    since: date | None = None
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").date()

    seen = existing_hashes(args.target)
    new_entries: list[str] = []
    skipped = 0

    review_files = sorted(args.reviews_dir.glob("*.md"))
    for rf in review_files:
        if rf.name == "_index.md":
            continue
        text = rf.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm.get("status") != "closed":
            continue
        if since and "date" in fm:
            try:
                rev_date = datetime.strptime(fm["date"], "%Y-%m-%d").date()
                if rev_date < since:
                    continue
            except ValueError:
                pass

        findings = extract_findings(text, severities)
        for f in findings:
            if pattern_hash(f["title"]) in seen:
                skipped += 1
                continue
            new_entries.append(render_entry(f, rf.name))
            seen.add(pattern_hash(f["title"]))

    if not new_entries:
        print(f"Nothing new to add. Skipped {skipped} already-present findings.")
        return 0

    if args.dry_run:
        print(f"[dry-run] Would append {len(new_entries)} entries to {args.target}")
        for e in new_entries:
            print(e)
        return 0

    args.target.parent.mkdir(parents=True, exist_ok=True)
    header = ""
    if not args.target.exists():
        header = (
            "# Anti-patterns\n\n"
            "Auto-extracted from closed reviews by `scripts/extract_patterns.py`. "
            "Edit freely — entries are matched by hash, not by content.\n\n"
        )

    with args.target.open("a", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        for e in new_entries:
            fh.write(e)

    print(f"Appended {len(new_entries)} new entries to {args.target}. Skipped {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
