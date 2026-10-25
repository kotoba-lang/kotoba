#!/usr/bin/env python3
"""Phase 3W: filtered WET -> Cypher (page text chunks), resumable.

Reads gzip WET files under /Volumes/251220/CC/2603/filtered/wet and emits:
  graph/wet_batch_XXXXXX.cypher

This keeps WET text separate from the existing WAT graph batches.
"""

import gzip
import hashlib
import json
import logging
import os
import re
import signal
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from warcio.archiveiterator import ArchiveIterator

BASE_DIR = Path(os.environ.get("CC_DATA_DIR", "/Volumes/251220/CC/2603"))
WET_DIR = BASE_DIR / "filtered" / "wet"
GRAPH_DIR = BASE_DIR / "graph"
STATE_FILE = BASE_DIR / "scripts" / ".phase3_wet_state.json"
CRAWL_ID = os.environ.get("CC_CRAWL_ID", "CC-MAIN-2026-12")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "scripts" / "phase3_wet.log"),
    ],
)
log = logging.getLogger(__name__)

shutdown_requested = False
NOISE_KEYWORDS = (
    "privacy policy",
    "terms of use",
    "cookie",
    "all rights reserved",
    "javascript enabled",
    "skip to main content",
    "sign in",
    "log in",
    "create account",
    "search",
    "menu",
    "home",
    "wikimedia",
    "wikipedia",
    "creativecommons",
    "powered by",
)
NOISE_TERMS = tuple(sorted(set(" ".join(NOISE_KEYWORDS).split())))
DEFAULT_EXCLUDED_DOMAIN_PATTERNS = (
    r"(^|\.)wikipedia\.org$",
    r"(^|\.)wikimedia\.org$",
    r"(^|\.)github\.com$",
    r"(^|\.)gitlab\.com$",
    r"(^|\.)agrovoc\.fao\.org$",
)
DOMAIN_REGEX = [re.compile(p) for p in DEFAULT_EXCLUDED_DOMAIN_PATTERNS]


def _sig(_signum, _frame):
    global shutdown_requested
    shutdown_requested = True


signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)


def esc(s: str) -> str:
    return (
        (s or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\u2028", " ")
        .replace("\u2029", " ")
        .replace("\u0085", " ")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def normalize_text(s: str) -> str:
    s = (s or "").replace("\u2028", " ").replace("\u2029", " ").replace("\u0085", " ")
    s = s.replace("\r", "\n")
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _looks_like_boilerplate(block: str) -> bool:
    low = block.lower()
    keyword_hits = sum(1 for k in NOISE_KEYWORDS if k in low)
    url_matches = re.findall(r"(?:https?://|www\.)\S+", low)
    url_count = len(url_matches)
    url_chars = sum(len(u) for u in url_matches)
    symbol_count = sum(1 for ch in block if not ch.isalnum() and not ch.isspace())
    symbol_ratio = symbol_count / max(len(block), 1)

    if keyword_hits >= 2:
        return True
    if url_count >= 3:
        return True
    if url_count >= 1 and (url_chars / max(len(block), 1)) >= 0.2:
        return True
    if url_count >= 2 and len(block) < 800:
        return True
    if low.count("|") >= 4 and len(block) < 500:
        return True
    if symbol_ratio >= 0.25 and len(block) < 700:
        return True
    return False


def _domain_excluded(domain: str) -> bool:
    return any(rx.search(domain) for rx in DOMAIN_REGEX)


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]{2,}", text.lower())


def _template_noise_ratio(text: str) -> float:
    toks = _tokenize_words(text)
    if not toks:
        return 1.0
    hits = sum(1 for t in toks if t in NOISE_TERMS)
    return hits / len(toks)


def _content_quality_ok(text: str, min_alpha_ratio: float = 0.35) -> bool:
    if len(text) < 120:
        return False
    alpha = sum(1 for ch in text if ch.isalpha())
    ratio = alpha / max(len(text), 1)
    if ratio < min_alpha_ratio:
        return False
    if _template_noise_ratio(text) > 0.18:
        return False
    return True


def _normalize_for_dedupe(text: str) -> str:
    text = re.sub(r"https?://\\S+", " ", text.lower())
    text = re.sub(r"\\b\\d+\\b", " ", text)
    text = re.sub(r"[^a-z\\s]", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def _simhash64(text: str) -> int:
    tokens = _normalize_for_dedupe(text).split()
    if not tokens:
        return 0
    v = [0] * 64
    for t in tokens:
        h = int(hashlib.blake2b(t.encode("utf-8"), digest_size=8).hexdigest(), 16)
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i, w in enumerate(v):
        if w > 0:
            out |= 1 << i
    return out


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class ChunkDeduper:
    def __init__(self, hamming_threshold: int = 3):
        self.hamming_threshold = hamming_threshold
        self.exact = set()
        self.bands = defaultdict(list)  # key -> list[simhash]

    def _band_keys(self, sim: int):
        mask = (1 << 16) - 1
        for i in range(4):
            yield (i, (sim >> (16 * i)) & mask)

    def seen_or_add(self, text: str) -> bool:
        norm = _normalize_for_dedupe(text)
        if len(norm) < 80:
            return False
        exact_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]
        if exact_hash in self.exact:
            return True
        sim = _simhash64(norm)
        for k in self._band_keys(sim):
            for prev in self.bands[k]:
                if _hamming(sim, prev) <= self.hamming_threshold:
                    return True
        self.exact.add(exact_hash)
        for k in self._band_keys(sim):
            self.bands[k].append(sim)
        return False


def extract_main_text(text: str, min_chars: int = 300) -> str:
    raw = (text or "").replace("\u2028", "\n").replace("\u2029", "\n").replace("\u0085", "\n").replace("\r", "\n")
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", raw)
    blocks = re.split(r"\n+|(?<=[.!?。！？])\s{2,}", raw)
    kept = []
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        if not b:
            continue
        if len(b) < 30:
            continue
        if _looks_like_boilerplate(b):
            continue
        kept.append(b)

    extracted = normalize_text(" ".join(kept))
    fallback = normalize_text(raw)
    if len(extracted) < min_chars:
        return fallback
    return extracted


def extract_domain(url: str) -> str:
    try:
        h = urlparse(url).hostname
        return h.lower() if h else ""
    except Exception:
        return ""


def domain_to_did(domain: str) -> str:
    return f"did:web:site.etzhayyim.com:{domain.replace('.', '-')}"


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        try:
            with open(state_file) as f:
                return json.load(f)
        except Exception:
            pass
    return {"files_done": [], "batch_id": 0, "total_chunks": 0}


def save_state(state: dict, state_file: Path) -> None:
    tmp = state_file.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, state_file)


def iter_text_chunks(text: str, max_chars: int = 1200):
    text = (text or "").strip()
    if not text:
        return
    i = 0
    while i < len(text):
        yield text[i:i + max_chars]
        i += max_chars


def generate_cypher(stmts: list[dict]) -> str:
    # Emit Domain/Page MERGE once per page, then append chunk records.
    pages = {}
    for s in stmts:
        p = pages.setdefault(
            s["page_rkey"],
            {
                "did": s["did"],
                "domain": s["domain"],
                "url": s["url"],
                "page_rkey": s["page_rkey"],
                "chunks": [],
            },
        )
        p["chunks"].append(s)

    lines = []
    for p in pages.values():
        lines.append(
            f'MERGE (d:DomainDID {{did: "{esc(p["did"])}"}}) '
            f'ON CREATE SET d.domain = "{esc(p["domain"])}", d.slug = "{esc(p["domain"].replace(".", "-"))}"'
        )
        lines.append(
            f'MERGE (p:PageRecord {{rkey: "{esc(p["page_rkey"])}"}}) '
            f'ON CREATE SET p.url = "{esc(p["url"][:2000])}", p.domainDid = "{esc(p["did"])}", '
            f'p.domain = "{esc(p["domain"])}", p.crawl = "{esc(CRAWL_ID)}"'
        )
        lines.append(
            f'MATCH (d:DomainDID {{did: "{esc(p["did"])}"}}), (p:PageRecord {{rkey: "{esc(p["page_rkey"])}"}}) '
            f'MERGE (d)-[:HOSTS_PAGE]->(p)'
        )
        for s in p["chunks"]:
            lines.append(
                f'MERGE (w:WetChunkRecord {{rkey: "{esc(s["chunk_rkey"])}"}}) '
                f'ON CREATE SET w.pageRkey = "{esc(s["page_rkey"])}", w.url = "{esc(s["url"][:2000])}", '
                f'w.chunkIndex = {s["chunk_idx"]}, w.text = "{esc(s["text"])}", w.crawl = "{esc(CRAWL_ID)}"'
            )
            lines.append(
                f'MATCH (p:PageRecord {{rkey: "{esc(s["page_rkey"])}"}}), (w:WetChunkRecord {{rkey: "{esc(s["chunk_rkey"])}"}}) '
                f'MERGE (p)-[:HAS_WET_CHUNK]->(w)'
            )
    return "\n".join(lines)


def process(
    batch_size: int = 2000,
    chunk_chars: int = 1200,
    no_resume: bool = False,
    output_prefix: str = "wet_batch",
    state_file: Path = STATE_FILE,
    max_files: int = 0,
):
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    state = {"files_done": [], "batch_id": 0, "total_chunks": 0} if no_resume else load_state(state_file)
    done = set(state.get("files_done", []))
    wet_files = sorted(WET_DIR.glob("*.gz"))
    remaining = [f for f in wet_files if f.name not in done]
    if max_files > 0:
        remaining = remaining[:max_files]
    log.info("WET files: total=%d remaining=%d", len(wet_files), len(remaining))

    batch_id = int(state.get("batch_id", 0))
    stmts = []
    deduper = ChunkDeduper(hamming_threshold=3)
    skipped_domain = 0
    skipped_quality = 0
    skipped_duplicate = 0

    for idx, wf in enumerate(remaining, start=1):
        if shutdown_requested:
            break
        log.info("Processing %d/%d %s", idx, len(remaining), wf.name)
        try:
            with gzip.open(wf, "rb") as fh:
                for rec in ArchiveIterator(fh):
                    if shutdown_requested:
                        break
                    if rec.rec_type not in ("conversion", "response", "resource"):
                        continue
                    url = rec.rec_headers.get_header("WARC-Target-URI") or ""
                    if not url.startswith("http"):
                        continue
                    domain = extract_domain(url)
                    if not domain:
                        continue
                    if _domain_excluded(domain):
                        skipped_domain += 1
                        continue
                    raw_text = rec.content_stream().read().decode("utf-8", errors="replace")
                    text = extract_main_text(raw_text)
                    if not text:
                        continue
                    if not _content_quality_ok(text):
                        skipped_quality += 1
                        continue
                    did = domain_to_did(domain)
                    page_rkey = url_hash(url)
                    for i, chunk in enumerate(iter_text_chunks(text, max_chars=chunk_chars)):
                        if deduper.seen_or_add(chunk):
                            skipped_duplicate += 1
                            continue
                        stmts.append(
                            {
                                "did": did,
                                "domain": domain,
                                "url": url,
                                "page_rkey": page_rkey,
                                "chunk_rkey": f"{page_rkey}_{i:04d}",
                                "chunk_idx": i,
                                "text": chunk,
                            }
                        )
                        state["total_chunks"] = int(state.get("total_chunks", 0)) + 1
                        if len(stmts) >= batch_size:
                            out = GRAPH_DIR / f"{output_prefix}_{batch_id:06d}.cypher"
                            with open(out, "w") as f:
                                f.write(generate_cypher(stmts))
                            log.info("  Batch %d: chunks=%d -> %s", batch_id, len(stmts), out.name)
                            stmts = []
                            batch_id += 1
        except Exception as e:
            log.error("Error processing %s: %s", wf.name, e)

        state["files_done"].append(wf.name)
        state["batch_id"] = batch_id
        save_state(state, state_file)

    if stmts:
        out = GRAPH_DIR / f"{output_prefix}_{batch_id:06d}.cypher"
        with open(out, "w") as f:
            f.write(generate_cypher(stmts))
        log.info("  Batch %d: chunks=%d -> %s", batch_id, len(stmts), out.name)
        batch_id += 1

    state["batch_id"] = batch_id
    save_state(state, state_file)
    log.info(
        "Done: total_chunks=%d, batches=%d, skipped_domain=%d, skipped_quality=%d, skipped_duplicate=%d",
        state.get("total_chunks", 0),
        batch_id,
        skipped_domain,
        skipped_quality,
        skipped_duplicate,
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Phase 3W: filtered WET -> Cypher")
    ap.add_argument("--batch-size", type=int, default=2000)
    ap.add_argument("--chunk-chars", type=int, default=1200)
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--output-prefix", type=str, default="wet_batch")
    ap.add_argument("--state-file", type=str, default=str(STATE_FILE))
    ap.add_argument("--max-files", type=int, default=0)
    args = ap.parse_args()
    process(
        batch_size=args.batch_size,
        chunk_chars=args.chunk_chars,
        no_resume=args.no_resume,
        output_prefix=args.output_prefix,
        state_file=Path(args.state_file),
        max_files=args.max_files,
    )
