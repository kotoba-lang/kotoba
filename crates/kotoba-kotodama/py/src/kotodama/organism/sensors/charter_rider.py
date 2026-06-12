"""Charter Compliance Rider §2(a)..(h) heuristic scanner.

Implements the scanner referenced in:

  - ADR-2605192200 (Charter Compliance Rider v2.0)
  - ADR-2605241500 §D7 (dataset substrate pre-pin gate)
  - CLAUDE.md baien tooling index

Phase 1 is a **heuristic regex scanner** — it catches obvious lexical
signals for each of the 8 prohibited categories. It does NOT make a
binding judgment; a `passed=False` result is a fail-closed gate that
forces human review. False positives are expected and acceptable:
operators tighten the pattern set (or mark a sample with a documented
exemption) and re-run.

Output shape matches the contract expected by
`e7m_dataset.charter.scan_sample`:

    {
      "passed": bool,
      "at": "<RFC3339>",
      "sampled": int,             # number of files actually inspected
      "violations": list[dict],   # per-hit findings (path, category, snippet)
      "note": str,                # short human summary
    }

The 8 categories map to ADR-2605192200 §2(a)..(h). Patterns are
deliberately conservative: they target product/marketing copy and
training-data style content that would propagate Rider-violating use
when fine-tuned. Tighten over time as we observe false positives.
"""

from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ── §2 category patterns ────────────────────────────────────────────


@dataclass(frozen=True)
class CategoryRule:
    code: str        # "2a", "2b", ...
    label: str
    pattern: re.Pattern[str]
    # Allowlist regex applied to the surrounding context (matched against
    # the line). If the line ALSO contains an allow-pattern, the hit is
    # demoted to a non-violation (counted as `false_positive`).
    allow_context: re.Pattern[str] | None = None


_RULES: tuple[CategoryRule, ...] = (
    CategoryRule(
        code="2a",
        label="WEAPONS AND MILITARY",
        pattern=re.compile(
            r"\b("
            r"assault\s+rifle"
            r"|lethal\s+autonomous"
            r"|kinetic\s+(weapon|strike)"
            r"|cyber[-\s]?offensive"
            r"|munition|warhead"
            r"|ammunition\s+(sale|purchase|stockpil)"
            r"|paramilitary\s+contractor"
            r"|kill[-\s]?chain"
            r")\b",
            re.IGNORECASE,
        ),
        allow_context=re.compile(
            r"\b(historical|treaty|disarm|ban\s+treaty|geneva|red\s+cross|red\s+crescent|antiwar|peace\s+research|forensic)\b",
            re.IGNORECASE,
        ),
    ),
    CategoryRule(
        code="2b",
        label="SPECULATIVE FINANCE",
        pattern=re.compile(
            r"\b("
            r"high[-\s]?frequency\s+trading"
            r"|hft\s+strateg"
            r"|predatory\s+(loan|lending)"
            r"|payday\s+loan"
            r"|leverage\s+spread"
            r"|arbitrage\s+bot"
            r"|naked\s+short"
            r"|pump\s+and\s+dump"
            r")\b",
            re.IGNORECASE,
        ),
        allow_context=re.compile(
            r"\b(critique|regulator|prosecut|fraud\s+report|consumer\s+protection|academic|case\s+study)\b",
            re.IGNORECASE,
        ),
    ),
    CategoryRule(
        code="2c",
        label="SURVEILLANCE CAPITALISM",
        pattern=re.compile(
            r"\b("
            r"ad[-\s]?tech\s+(dsp|ssp)"
            r"|data\s+broker"
            r"|behavioral\s+targeting"
            r"|cross[-\s]?site\s+tracking"
            r"|fingerprint(ing|er)\s+(sdk|library|user)"
            r"|biometric\s+(id|identification)\s+(for\s+)?(police|military|enforcement)"
            r"|facial\s+recognition\s+(deployed|sold|licens)"
            r")\b",
            re.IGNORECASE,
        ),
        allow_context=re.compile(
            r"\b(privacy|countermeasure|defens|audit|ePrivacy|GDPR|critique|investigation)\b",
            re.IGNORECASE,
        ),
    ),
    CategoryRule(
        code="2d",
        label="FOSSIL FUEL EXTRACTION (NEW)",
        pattern=re.compile(
            r"\b("
            r"new\s+(coal|oil|gas)\s+(field|extraction|project|lease)"
            r"|greenfield\s+(coal|oil|gas)"
            r"|fracking\s+(initiation|new\s+well|lease)"
            r"|deep[-\s]?water\s+(oil|gas)\s+(initiat|new)"
            r"|tar\s+sands\s+(initiat|new\s+lease)"
            r")\b",
            re.IGNORECASE,
        ),
        allow_context=re.compile(
            r"\b(decommission|transition|renewable\s+transition|stranded\s+asset|just\s+transition|critique)\b",
            re.IGNORECASE,
        ),
    ),
    CategoryRule(
        code="2e",
        label="SPECIALIST GATEKEEPING",
        pattern=re.compile(
            r"\b("
            r"mandatory\s+(consult|fee)\s+for\s+publicly\s+available"
            r"|gatekeep\w*\s+licensure"
            r"|artificial(ly)?\s+restrict\w*\s+access\s+to\s+(medical|legal)\s+knowledge"
            r"|admin(istrative)?\s+fee\s+for\s+legally\s+required\s+interaction"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    CategoryRule(
        code="2f",
        label="MULTI-GENERATIONAL HARM",
        pattern=re.compile(
            r"\b("
            r"germline\s+(edit|modification)\s+without\s+(safety|review)"
            r"|biosphere\s+collapse\s+(profit|investment\s+opportunit)"
            r"|attention\s+monopol\w*\s+target\w*\s+(child|adolescen|developing)"
            r"|addictive\s+design\s+(child|teen|adolescen)"
            r"|information\s+monoculture\s+(scale|deploy|monetiz)"
            r")\b",
            re.IGNORECASE,
        ),
        allow_context=re.compile(
            r"\b(critique|prevent|harm[-\s]?reduction|safety\s+review|academic|public\s+health)\b",
            re.IGNORECASE,
        ),
    ),
    CategoryRule(
        code="2g",
        label="STRICT INDIVIDUALIST ONTOLOGY",
        pattern=re.compile(
            r"\b("
            r"objectivis(m|t)\s+(party|institute|society|advocacy)"
            r"|atlas\s+shrugged\s+(institute|advocacy)"
            r"|abolish\s+(public|collective)\s+(infrastructure|good)"
            r"|individual\s+is\s+the\s+constitutive\s+(ontological|moral)\s+unit"
            r"|strict\s+individualis(m|t)\s+(platform|advocacy|campaign)"
            r")\b",
            re.IGNORECASE,
        ),
        allow_context=re.compile(
            r"\b(critique|response|rebuttal|history\s+of\s+philosophy|academic|comparative)\b",
            re.IGNORECASE,
        ),
    ),
    CategoryRule(
        code="2h",
        label="WELLBECOMING SUBORDINATION VIOLATION",
        pattern=re.compile(
            r"\b("
            r"engagement\s+optimi[sz]ation\s+at\s+(any\s+cost|expense)"
            r"|maximi[sz]e\s+dwell\s+time"
            r"|dark\s+pattern\s+(deploy|conversion)"
            r"|financiali[sz]ation\s+of\s+(housing|healthcare|water|food|education)"
            r"|pre[-\s]?trained\s+(llm|ai)\s+without\s+(safety|cognitive\s+sovereignty)"
            r")\b",
            re.IGNORECASE,
        ),
        allow_context=re.compile(
            r"\b(critique|defens|opposed|harm[-\s]?reduction|academic)\b",
            re.IGNORECASE,
        ),
    ),
)


# Filename extensions we treat as text-scannable.
_TEXT_EXTS = {".txt", ".md", ".rst", ".json", ".jsonl", ".csv", ".tsv", ".sparql", ".html", ".htm", ".xml", ".yaml", ".yml"}


@dataclass
class _Finding:
    path: str
    category_code: str
    category_label: str
    line_no: int
    snippet: str

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "categoryCode": self.category_code,
            "categoryLabel": self.category_label,
            "lineNo": self.line_no,
            "snippet": self.snippet,
        }


@dataclass
class _RunStats:
    sampled_files: int = 0
    sampled_lines: int = 0
    skipped_binary: int = 0
    false_positives: int = 0
    findings: list[_Finding] = field(default_factory=list)


def _is_text(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTS:
        return True
    # Probe the first KB for binary bytes.
    try:
        chunk = path.read_bytes()[:1024]
    except OSError:
        return False
    return b"\x00" not in chunk


def _iter_lines(path: Path, max_lines: int) -> Iterable[tuple[int, str]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                if i > max_lines:
                    return
                yield i, line.rstrip("\n")
    except OSError:
        return


def _scan_one(path: Path, sample_rows: int, stats: _RunStats) -> None:
    if not _is_text(path):
        stats.skipped_binary += 1
        return
    stats.sampled_files += 1
    for i, line in _iter_lines(path, sample_rows):
        stats.sampled_lines += 1
        for rule in _RULES:
            m = rule.pattern.search(line)
            if not m:
                continue
            if rule.allow_context and rule.allow_context.search(line):
                stats.false_positives += 1
                continue
            snippet = line.strip()
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            stats.findings.append(_Finding(
                path=str(path),
                category_code=rule.code,
                category_label=rule.label,
                line_no=i,
                snippet=snippet,
            ))


def scan(
    sample_paths: Iterable[Path],
    *,
    kind: str = "reference",
    sample_rows: int = 200,
) -> dict:
    """Scan `sample_paths` for Charter Rider §2(a)..(h) signals.

    Returns a dict with the shape expected by
    `e7m_dataset.charter.scan_sample`. Per-file scan is line-oriented
    and capped at `sample_rows` lines (defensive against huge files).
    """
    stats = _RunStats()
    for p in sample_paths:
        path = Path(p)
        if path.is_dir() or not path.exists():
            continue
        _scan_one(path, sample_rows, stats)

    passed = not stats.findings
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    note = (
        f"sampled {stats.sampled_files} files / {stats.sampled_lines} lines; "
        f"{len(stats.findings)} hits, {stats.false_positives} demoted by allow-context"
    )
    return {
        "passed": passed,
        "at": now,
        "sampled": stats.sampled_files,
        "violations": [f.as_dict() for f in stats.findings],
        "note": note,
    }


def scan_text(text: str, *, label: str = "<text>", sample_rows: int = 10_000) -> dict:
    """Scan an in-memory string for Charter Rider §2(a)..(h) signals.

    Pure + dependency-free (no file I/O, no tempfile, no normalizer) — the
    lightweight path for gating a record/observation at ingest time (G1).
    Returns the same dict shape as :func:`scan` (``passed`` / ``violations`` /
    ``note``). Line-oriented and capped at ``sample_rows`` lines.
    """
    stats = _RunStats()
    stats.sampled_files = 1
    for i, line in enumerate(text.splitlines(), start=1):
        if i > sample_rows:
            break
        stats.sampled_lines += 1
        for rule in _RULES:
            if not rule.pattern.search(line):
                continue
            if rule.allow_context and rule.allow_context.search(line):
                stats.false_positives += 1
                continue
            snippet = line.strip()
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            stats.findings.append(_Finding(
                path=label,
                category_code=rule.code,
                category_label=rule.label,
                line_no=i,
                snippet=snippet,
            ))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "passed": not stats.findings,
        "at": now,
        "sampled": stats.sampled_files,
        "violations": [f.as_dict() for f in stats.findings],
        "note": (
            f"scanned {stats.sampled_lines} lines; {len(stats.findings)} hits, "
            f"{stats.false_positives} demoted by allow-context"
        ),
    }


def is_clean(text: str) -> bool:
    """True if ``text`` shows no Charter Rider §2 violation (allow-context aware)."""
    return scan_text(text)["passed"]


def scan_with_normalization(text: str) -> dict:
    """Normalize input text and scan it for violations.

    Returns the same dict shape as `scan()`, but operates on a single string
    after applying adversarial normalization (NFKC, de-obfuscation).
    """
    import tempfile
    from kotodama.organism.adversarial.normalizer import normalize_input

    # 1. Normalize
    res = normalize_input(text)

    # 2. Write to temp file to reuse existing line-oriented `scan`
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write(res.normalized)
        temp_path = Path(f.name)

    try:
        # 3. Scan the normalized text
        scan_res = scan([temp_path], kind="normalized_text")
        # Add normalization context if suspicious
        if res.suspicious:
            scan_res["note"] = f"[SUSPICIOUS INPUT DETECTED] {scan_res['note']}"
            scan_res["suspicious"] = True
            scan_res["normalization_transforms"] = res.transforms
        return scan_res
    finally:
        if temp_path.exists():
            temp_path.unlink()


__all__ = ["scan", "scan_text", "is_clean", "scan_with_normalization"]
