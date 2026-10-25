"""Read package.edn / status.edn without full EDN parser (subset we need)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _parse_simple_edn_map(text: str) -> Dict[str, Any]:
    """Parse a flat-ish EDN map of keywords → string/keyword/vector-of-strings.

    Good enough for our package.edn / status.edn; not a full EDN reader.
    """
    out: Dict[str, Any] = {}
    # keyword string
    for m in re.finditer(r":([a-zA-Z0-9_./-]+)\s+\"([^\"]*)\"", text):
        out[m.group(1)] = m.group(2)
    # keyword keyword
    for m in re.finditer(r":([a-zA-Z0-9_./-]+)\s+:([a-zA-Z0-9_./-]+)", text):
        k, v = m.group(1), m.group(2)
        if k not in out:
            out[k] = v
    # keyword vector of strings
    for m in re.finditer(r":([a-zA-Z0-9_./-]+)\s+\[([^\]]*)\]", text):
        k = m.group(1)
        inner = m.group(2)
        strs = re.findall(r"\"([^\"]*)\"", inner)
        kws = re.findall(r":([a-zA-Z0-9_./-]+)", inner)
        if strs:
            out[k] = strs
        elif kws and k not in out:
            out[k] = kws
    return out


def load_package(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    raw = _parse_simple_edn_map(text)
    # normalize keys without submission/ prefix duplicates
    pkg = {
        "id": raw.get("submission/id") or raw.get("id"),
        "title": raw.get("submission/title") or raw.get("title"),
        "primary": raw.get("submission/primary-category") or raw.get("primary") or "cs.LG",
        "cross_lists": raw.get("submission/cross-lists") or raw.get("cross-lists") or [],
        "license": raw.get("submission/license") or "cc-by-4.0",
        "comments": raw.get("submission/comments") or "",
        "source_dir": raw.get("submission/source-dir") or "source",
        "source_archive": raw.get("submission/source-archive") or "",
        "abstract_file": raw.get("submission/abstract-file") or "abstract.txt",
        "final_requires": raw.get("submission/final-submit-requires") or "human-approval",
        "raw": raw,
        "path": str(path),
        "root": str(path.parent),
    }
    return pkg


def load_status(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"state": "draft"}
    raw = _parse_simple_edn_map(path.read_text(encoding="utf-8"))
    return {
        "state": raw.get("submission/state") or raw.get("state") or "draft",
        "draft_id": raw.get("submission/arxiv-draft-id") or raw.get("arxiv-draft-id"),
        "url": raw.get("submission/url") or raw.get("url"),
        "account": raw.get("submission/arxiv-account") or raw.get("arxiv-account"),
        "raw": raw,
        "path": str(path),
    }


def resolve_archive(pkg: Dict[str, Any], root: Path) -> Path:
    rel = pkg.get("source_archive") or ""
    # package paths are often relative to arxiv repo root (submissions/...)
    candidates = [
        root / rel,
        Path(rel),
        root / "build" / Path(rel).name,
        Path(pkg["root"]) / "build" / Path(rel).name,
        Path(pkg["root"]) / "build" / "sqrt_space_kv-arxiv-source.tar.gz",
    ]
    for c in candidates:
        if c and c.exists():
            return c.resolve()
    raise FileNotFoundError(
        f"source archive not found; tried {[str(c) for c in candidates]}"
    )


def resolve_abstract(pkg: Dict[str, Any]) -> str:
    root = Path(pkg["root"])
    rel = pkg.get("abstract_file") or "abstract.txt"
    for c in [root / Path(rel).name, root / rel, Path(rel)]:
        if c.exists():
            return c.read_text(encoding="utf-8").strip()
    # fallback: title only
    return pkg.get("title") or ""


def write_status(path: Path, fields: Dict[str, Any]) -> None:
    """Write a minimal status.edn (overwrites)."""
    lines = ["{"]
    mapping = {
        "id": ":submission/id",
        "state": ":submission/state",
        "draft_id": ":submission/arxiv-draft-id",
        "url": ":submission/url",
        "account": ":submission/arxiv-account",
        "email": ":submission/arxiv-email",
        "primary": ":submission/primary-category",
        "updated_at": ":submission/updated-at",
    }
    # id as keyword if looks like keyword
    if "id" in fields:
        vid = fields["id"]
        if isinstance(vid, str) and not vid.startswith(":"):
            lines.append(f" :submission/id :{vid}")
        else:
            lines.append(f" :submission/id {vid}")
    for k, edn_k in mapping.items():
        if k == "id" or k not in fields or fields[k] is None:
            continue
        v = fields[k]
        if k == "state":
            lines.append(f" {edn_k} :{v}")
        else:
            lines.append(f' {edn_k} "{v}"')
    if fields.get("cross_lists"):
        xs = " ".join(f'"{x}"' for x in fields["cross_lists"])
        lines.append(f" :submission/cross-lists [{xs}]")
    if fields.get("notes"):
        notes = "\n".join(f'  "{n}"' for n in fields["notes"])
        lines.append(f" :submission/notes\n [{notes}]")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
