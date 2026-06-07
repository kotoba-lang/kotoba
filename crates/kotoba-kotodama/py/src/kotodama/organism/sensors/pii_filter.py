"""PII redactor — runs before the Charter Rider §2 scan.

Per ADR-2605262400 §6. Wave-1 scope:

  - email addresses (RFC-5321 grammar, regex-only — no live DNS check;
    sensors are PASSIVE-ONLY per ADR-2605262400 §7);
  - E.164 phone numbers (with international prefix);
  - postal-address-shaped lines with a 2-letter country code (heuristic;
    conservative — over-redact rather than under);
  - WHOIS registrant blocks (`registrant: ...`, `tech-c: ...`,
    `admin-c: ...`, `e-mail: ...`).

Policy: matches are **redacted in place**. Original bytes are
preserved in the DataLad annex; the redacted view is what sensors and
the corpus assembler see. The Charter Rider §2 scan runs on the
redacted view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .base import PiiFilterPolicy


_REDACT = "[redacted-pii]"


_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}\b"
)

_PHONE_RE = re.compile(
    r"(?<!\d)\+(?:\d[\s\-.()]?){6,14}\d(?!\d)"
)

_WHOIS_KEYS_RE = re.compile(
    r"^(?P<key>\s*(?:registrant|admin[-_ ]?c|tech[-_ ]?c|e[-_ ]?mail|"
    r"contact|address|phone|fax|registrant[-_ ]?name|registrant[-_ ]?email|"
    r"registrant[-_ ]?phone|registrant[-_ ]?street|"
    r"registrant[-_ ]?city|registrant[-_ ]?postal[-_ ]?code|"
    r"registrant[-_ ]?country|abuse[-_ ]?contact[-_ ]?email|"
    r"abuse[-_ ]?contact[-_ ]?phone))\s*[:=]\s*(?P<val>.+?)\s*$",
    re.IGNORECASE,
)

_POSTAL_RE = re.compile(
    r"(?:[^,]+,\s*){2,}[^,]*?\b\d{3,10}\b[^,]*?,\s*[A-Z]{2}\s*$",
    re.MULTILINE,
)


@dataclass
class RedactionStats:
    emails: int = 0
    phones: int = 0
    whois_values: int = 0
    postal_lines: int = 0

    @property
    def total(self) -> int:
        return self.emails + self.phones + self.whois_values + self.postal_lines

    def merged(self, other: "RedactionStats") -> "RedactionStats":
        return RedactionStats(
            emails=self.emails + other.emails,
            phones=self.phones + other.phones,
            whois_values=self.whois_values + other.whois_values,
            postal_lines=self.postal_lines + other.postal_lines,
        )


def redact_emails(text: str, stats: RedactionStats | None = None) -> str:
    if stats is None:
        stats = RedactionStats()
    def _sub(m: re.Match[str]) -> str:
        stats.emails += 1
        return _REDACT
    return _EMAIL_RE.sub(_sub, text)


def redact_phones(text: str, stats: RedactionStats | None = None) -> str:
    if stats is None:
        stats = RedactionStats()
    def _sub(m: re.Match[str]) -> str:
        stats.phones += 1
        return _REDACT
    return _PHONE_RE.sub(_sub, text)


def redact_whois_values(text: str, stats: RedactionStats | None = None) -> str:
    if stats is None:
        stats = RedactionStats()
    out_lines: list[str] = []
    for line in text.splitlines(keepends=False):
        m = _WHOIS_KEYS_RE.match(line)
        if m:
            stats.whois_values += 1
            out_lines.append(f"{m.group('key')}: {_REDACT}")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def redact_postal(text: str, stats: RedactionStats | None = None) -> str:
    if stats is None:
        stats = RedactionStats()
    def _sub(m: re.Match[str]) -> str:
        stats.postal_lines += 1
        return _REDACT
    return _POSTAL_RE.sub(_sub, text)


def redact_text(
    text: str,
    *,
    policy: PiiFilterPolicy = PiiFilterPolicy.STRICT,
) -> tuple[str, RedactionStats]:
    """Apply the full PII filter pipeline to `text`.

    `policy == OFF` short-circuits (returns text unchanged). Production
    callers MUST NOT pass OFF — it exists only so unit tests with
    synthetic fixtures can be authored without redaction noise.
    """
    if policy is PiiFilterPolicy.OFF:
        return text, RedactionStats()

    stats = RedactionStats()
    out = text
    out = redact_whois_values(out, stats)
    out = redact_emails(out, stats)
    out = redact_phones(out, stats)
    out = redact_postal(out, stats)
    return out, stats


def redact_payload(
    payload: dict,
    *,
    policy: PiiFilterPolicy = PiiFilterPolicy.STRICT,
    fields: Iterable[str] | None = None,
) -> tuple[dict, RedactionStats]:
    """Redact string-valued fields in a dict.

    When `fields` is None, every string-typed value is run through
    `redact_text`. When provided, only those fields are touched (used
    by sensors that already know which payload columns are PII-risky).
    """
    stats = RedactionStats()
    if policy is PiiFilterPolicy.OFF:
        return dict(payload), stats

    if fields is None:
        target_keys = [k for k, v in payload.items() if isinstance(v, str)]
    else:
        target_keys = list(fields)

    out: dict = dict(payload)
    for k in target_keys:
        v = out.get(k)
        if not isinstance(v, str):
            continue
        redacted, sub_stats = redact_text(v, policy=policy)
        out[k] = redacted
        stats = stats.merged(sub_stats)
    return out, stats


__all__ = [
    "PiiFilterPolicy",
    "RedactionStats",
    "redact_emails",
    "redact_payload",
    "redact_phones",
    "redact_postal",
    "redact_text",
    "redact_whois_values",
]
