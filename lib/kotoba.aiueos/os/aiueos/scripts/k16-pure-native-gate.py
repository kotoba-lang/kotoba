#!/usr/bin/env python3
"""k16-pure-native-gate.py -- the K16 pure-native NEGATIVE gate, Node-free.

This is a faithful port of `k16-pure-native-gate.cljk` (which stays in the
tree as the dev-time oracle `check-image-route-node-free.py` measures this
against). The nbb original is a Node host, and `build-uefi.sh` REFUSED to
build without it -- NBB/Node sat inside the accepted build path, which the
JUN-31 acceptance criteria exclude (no C, NBB/Node, JVM or GraalVM path;
Python is orchestration only). Exit codes, marker lines, reason literals and
the receipt EDN VALUE are kept identical to the original; the original's doc
comment is the policy source of truth:

  k16-pure-native-gate.py --link-list <file> --provenance <file-or-dir>
                          [--receipt-out <file>] [--root <dir>] [object ...]

  Exit 0 = every input admitted.
  Exit 2 = COULD NOT ANSWER (no link list, empty link list, an input that is
           not on disk, a provenance manifest that does not read).
  Exit 3 = REFUSED: at least one input is foreign.

WHY 2 AND 3 ARE DIFFERENT CODES: a check that could not run must not return
the value of a check that ran and found nothing. `scanned=0` is exit 2 and
never a pass.

WHAT THIS IS NOT: it does not compile anything, and it does not claim the
committed objects reproduce byte-for-byte from their sources. What it
answers: is every byte entering this link accounted for by a Kotoba source
and an Amu revision that the repository records?

Receipt text is NOT byte-comparable with the cljk original (cljs pr-str
iterates hash maps in hash order, this writer in insertion order); every
reader sees the same EDN value, and the parity harness compares values.
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edn_lite import EdnError, Kw, pr_str, read_edn  # noqa: E402

TARGET = "x86_64-aiueos-kernel-v1"

# The exact section set `verify-kotoba-kernel-object.py` requires. A Kotoba
# kernel object must carry all seven and nothing else; a toolchain stub may
# carry a subset. Anything outside the set is how a C-derived object announces
# itself even when its receipt lies about the source.
ALLOWED_SECTIONS = frozenset(
    ["", ".text", ".data", ".rela.text", ".symtab", ".strtab", ".shstrtab"])
STUB_REQUIRED_SECTIONS = frozenset(
    ["", ".text", ".symtab", ".strtab", ".shstrtab"])
FOREIGN_SOURCE_EXTENSIONS = frozenset(
    [".c", ".h", ".S", ".s", ".asm", ".inc", ".cc", ".cpp", ".rs"])

# Reason literals. Pinned: the tests assert on these strings.
FOREIGN_REASONS = frozenset([
    "archive", "not-elf", "elf-type", "machine", "elf-header", "sections",
    "export", "undefined-symbol", "relocation", "receipt-missing",
    "receipt-shape", "c-source", "target", "object-sha256-mismatch",
    "source-missing", "source-sha256-mismatch"])
# Not a claim of foreign code: the object conforms and its digests match,
# but no record says WHICH Amu revision produced it.
UNATTESTED_REASONS = frozenset(["compiler-unrecorded"])
REASONS = FOREIGN_REASONS | UNATTESTED_REASONS


# ---------------------------------------------------------------- bytes ----

def read_bytes(p: str):
    try:
        with open(p, "rb") as f:
            return f.read()
    except OSError:
        return None


def sha256_hex(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def u8(b: bytes, off: int) -> int:
    return b[off]


def u16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def u64(b: bytes, off: int) -> int:
    return struct.unpack_from("<Q", b, off)[0]


def i64(b: bytes, off: int) -> int:
    return struct.unpack_from("<q", b, off)[0]


# ------------------------------------------------------------------ ELF ----

ELF64_IDENT = bytes([0x7F, 0x45, 0x4C, 0x46, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])


def cstring(buf: bytes, off: int):
    if off >= len(buf):
        return None
    end = buf.find(b"\x00", off)
    if end < 0:
        end = len(buf)
    return buf[off:end].decode("latin1")


def parse_elf(buf: bytes):
    """Parse an ELF64 relocatable object, fail-closed. Returns either
    `{"error": <reason literal>}` or a map of what the gate needs. Nothing
    here tolerates a surprise: a table that does not fit the file, a string
    that is not terminated, a section count outside the shape this target
    emits."""
    n = len(buf)
    if n >= 8 and buf[:8] == b"!<arch>\n":
        return {"error": "archive"}
    if n < 64:
        return {"error": "not-elf"}
    if bytes(buf[:16]) != ELF64_IDENT:
        return {"error": "not-elf"}
    etype = u16(buf, 16)
    machine = u16(buf, 18)
    version = u32(buf, 20)
    entry = u64(buf, 24)
    phoff = u64(buf, 32)
    shoff = u64(buf, 40)
    flags = u32(buf, 48)
    ehsize = u16(buf, 52)
    phentsize = u16(buf, 54)
    phnum = u16(buf, 56)
    shentsize = u16(buf, 58)
    shnum = u16(buf, 60)
    shstrndx = u16(buf, 62)
    if etype != 1:
        return {"error": "elf-type"}
    if machine != 62:
        return {"error": "machine"}
    if [version, entry, phoff, phnum, flags, ehsize, shentsize] != [1, 0, 0, 0, 0, 64, 64]:
        return {"error": "elf-header"}
    # `verify-kotoba-kernel-object.py` caps shnum at 16 and calls the overflow
    # "invalid section table bounds". This gate does NOT: a C object has 24
    # sections, and reporting that as a malformed header instead of a
    # section-set violation would name the wrong cause. The bound that matters
    # for parsing is that the table fits the file.
    if shnum == 0 or shstrndx >= shnum or shoff + shnum * 64 > n:
        return {"error": "elf-header"}

    sections = []
    for i in range(shnum):
        o = shoff + i * 64
        sections.append({
            "name-off": u32(buf, o),
            "type": u32(buf, o + 4),
            "flags": u64(buf, o + 8),
            "offset": u64(buf, o + 24),
            "size": u64(buf, o + 32),
            "link": u32(buf, o + 40),
            "info": u32(buf, o + 44),
            "entsize": u64(buf, o + 56),
        })

    def bytes_of(s):
        if s["type"] == 8:  # SHT_NOBITS
            return b""
        if s["offset"] + s["size"] > n:
            return None
        return bytes(buf[s["offset"]:s["offset"] + s["size"]])

    if any(bytes_of(s) is None for s in sections):
        return {"error": "elf-header"}
    shstr = bytes_of(sections[shstrndx])
    assert shstr is not None  # the check above guarantees every slice fits
    names = [cstring(shstr, s["name-off"]) for s in sections]
    if any(x is None for x in names):
        return {"error": "elf-header"}
    for s, nm in zip(sections, names):
        s["name"] = nm
    idx = {}
    for i, s in enumerate(sections):
        idx.setdefault(s["name"], i)

    symtab = idx.get(".symtab")
    strtab = idx.get(".strtab")
    symbols = None
    if symtab is not None and strtab is not None:
        sb = bytes_of(sections[symtab])
        st = bytes_of(sections[strtab])
        assert sb is not None and st is not None
        if len(sb) % 24 == 0:
            symbols = []
            for i in range(len(sb) // 24):
                o = i * 24
                nm = cstring(st, u32(sb, o))
                symbols.append({
                    "name": nm if nm is not None else "",
                    "info": u8(sb, o + 4),
                    "other": u8(sb, o + 5),
                    "shndx": u16(sb, o + 6),
                    "value": u64(sb, o + 8),
                    "size": u64(sb, o + 16),
                })

    rela_idx = idx.get(".rela.text")
    relas = None
    if rela_idx is not None:
        rb = bytes_of(sections[rela_idx])
        assert rb is not None
        if len(rb) % 24 == 0:
            relas = []
            for i in range(len(rb) // 24):
                o = i * 24
                # r_info is one u64 whose high half is the symbol index and
                # low half the type. Read as two LE u32s: shifting coerces to
                # int32 in cljs and would truncate.
                relas.append({
                    "offset": u64(rb, o),
                    "type": u32(rb, o + 8),
                    "sym": u32(rb, o + 12),
                    "addend": i64(rb, o + 16),
                })

    if symbols is None:
        return {"error": "elf-header"}
    if rela_idx is not None and relas is None:
        return {"error": "elf-header"}
    text_i = idx.get(".text")
    text_size = sections[text_i]["size"] if text_i is not None else 0
    return {"sections": sections, "names": names, "index": idx,
            "symbols": symbols, "relas": relas if relas is not None else [],
            "text-size": text_size}


# ----------------------------------------------------------- structure ----

def undefined_symbols(elf: dict):
    return [s["name"] for s in elf["symbols"] if s["shndx"] == 0 and s["name"]]


def global_funcs(elf: dict):
    return [s for s in elf["symbols"] if s["info"] == 0x12]


def check_kotoba_structure(elf: dict):
    """The same seven assertions `verify-kotoba-kernel-object.py` makes, in
    the same order, so a disagreement between the two is a bug in one of them
    and not a difference of policy."""
    idx, names = elf["index"], elf["names"]
    if set(names) != set(ALLOWED_SECTIONS) or len(names) != len(ALLOWED_SECTIONS):
        return {"reason": "sections"}
    t = elf["sections"][idx[".text"]]
    if t["type"] != 1 or not (t["flags"] & 4):
        return {"reason": "sections"}
    s = elf["sections"][idx[".data"]]
    if s["type"] != 1 or (s["flags"] & 4):
        return {"reason": "sections"}
    s = elf["sections"][idx[".symtab"]]
    if s["type"] != 2 or s["entsize"] != 24 or s["link"] != idx[".strtab"]:
        return {"reason": "sections"}
    undef = undefined_symbols(elf)
    if undef:
        return {"reason": "undefined-symbol", "imports": undef}
    gf = global_funcs(elf)
    if len(gf) != 1:
        return {"reason": "export"}
    name = gf[0]["name"]
    other, shndx, size = gf[0]["other"], gf[0]["shndx"], gf[0]["size"]
    rela = elf["sections"][idx[".rela.text"]]
    if not name.startswith("kotoba_aiueos_"):
        return {"reason": "export"}
    if other != 0 or shndx != idx[".text"] or size == 0:
        return {"reason": "export"}
    if (rela["type"] != 4 or rela["entsize"] != 24 or rela["size"] != 24
            or rela["link"] != idx[".symtab"] or rela["info"] != idx[".text"]):
        return {"reason": "relocation"}
    r = elf["relas"][0] if elf["relas"] else None
    if r is None or r["type"] != 2 or r["addend"] != -4:
        return {"reason": "relocation"}
    if r["sym"] >= len(elf["symbols"]):
        return {"reason": "relocation"}
    if elf["symbols"][r["sym"]]["shndx"] != idx[".data"]:
        return {"reason": "relocation"}
    if r["offset"] + 4 > elf["text-size"]:
        return {"reason": "relocation"}
    return {"export": name}


def check_stub_structure(elf: dict):
    """A toolchain stub is a fixed sequence Amu emits (an interrupt entry, a
    context switch): it has no Kotoba source, so the export-name and single
    relocation rules do not apply. Everything that keeps foreign bytes out
    still does -- section set, zero imports."""
    names = set(elf["names"])
    if not all(n in ALLOWED_SECTIONS for n in names):
        return {"reason": "sections"}
    if not all(n in names for n in STUB_REQUIRED_SECTIONS):
        return {"reason": "sections"}
    undef = undefined_symbols(elf)
    if undef:
        return {"reason": "undefined-symbol", "imports": undef}
    gf = global_funcs(elf)
    return {"export": gf[0]["name"] if gf else None}


# ------------------------------------------------------------ receipts ----

HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def hex40(s) -> bool:
    return isinstance(s, str) and HEX40.fullmatch(s) is not None


def hex64(s) -> bool:
    return isinstance(s, str) and HEX64.fullmatch(s) is not None


def path_extname(p: str) -> str:
    """Node `path.extname` semantics (not os.path.splitext): a leading-dot
    basename like `.kotoba` has no extension."""
    base = p.replace("\\", "/").rsplit("/", 1)[-1]
    dot = base.rfind(".")
    return "" if dot <= 0 else base[dot:]


def foreign_source(s) -> bool:
    return isinstance(s, str) and path_extname(s).lower() in FOREIGN_SOURCE_EXTENSIONS


def _get(m, k):
    return m.get(Kw(k)) if isinstance(m, dict) else None


def classify(obj: str, buf: bytes, receipt, root: str):
    """One object -> `{"class": ...}` or `{"reason": <literal>}`. Order
    matters and is the point: the most specific statement of foreignness
    wins, so a C object carrying a receipt that names its `.c` is refused as
    `c-source` rather than as whatever structural surprise its sections
    happen to produce first."""
    sha = sha256_hex(buf)
    if receipt is None:
        return {"reason": "receipt-missing", "sha256": sha}
    if not isinstance(receipt, dict):
        return {"reason": "receipt-shape", "sha256": sha}

    src = _get(receipt, "source")
    c_sources = _get(receipt, "c-sources")
    if foreign_source(src) or c_sources:
        out_c = []
        if foreign_source(src):
            out_c.append(src)
        if c_sources:
            out_c.extend(c_sources)
        return {"reason": "c-source", "sha256": sha, "c-sources": out_c}

    if not hex64(_get(receipt, "object-sha256")):
        return {"reason": "receipt-shape", "sha256": sha}
    if sha != _get(receipt, "object-sha256"):
        return {"reason": "object-sha256-mismatch", "sha256": sha}
    if _get(receipt, "target") != TARGET:
        return {"reason": "target", "sha256": sha}
    compiler = _get(receipt, "compiler")
    csha = compiler.get(Kw("sha")) if isinstance(compiler, dict) else None
    if not hex40(csha):
        return {"reason": "compiler-unrecorded", "sha256": sha}

    elf = parse_elf(buf)
    if elf.get("error"):
        return {"reason": elf["error"], "sha256": sha}
    stub = _get(receipt, "producer") == Kw("amu-toolchain-stub")
    verdict = check_stub_structure(elf) if stub else check_kotoba_structure(elf)
    if verdict.get("reason"):
        return {**verdict, "sha256": sha}
    if stub:
        if isinstance(_get(receipt, "stub"), Kw):
            return {"class": "toolchain-stub", "sha256": sha,
                    "export": verdict.get("export"), "stub": _get(receipt, "stub")}
        return {"reason": "receipt-shape", "sha256": sha}

    if not (isinstance(src, str) and src.endswith(".kotoba")):
        return {"reason": "receipt-shape", "sha256": sha}
    src_path = os.path.join(root, src) if isinstance(src, str) else None
    src_buf = read_bytes(src_path) if src_path else None
    if src_buf is None:
        return {"reason": "source-missing", "sha256": sha}
    if not hex64(_get(receipt, "source-sha256")):
        return {"reason": "receipt-shape", "sha256": sha}
    if sha256_hex(src_buf) != _get(receipt, "source-sha256"):
        return {"reason": "source-sha256-mismatch", "sha256": sha}
    return {"class": "kotoba-object", "sha256": sha,
            "export": verdict.get("export"), "source": src}


# ---------------------------------------------------------------- input ----

UNREADABLE = object()


def die(code: int, *msg) -> None:
    print(" ".join(str(m) for m in msg), file=sys.stderr)
    sys.exit(code)


def read_edn_file(p: str):
    try:
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return UNREADABLE
    try:
        return read_edn(text)
    except EdnError:
        return UNREADABLE


def load_provenance(p):
    """A manifest file (basename -> receipt) or a directory of
    `<basename>.edn`. Both shapes exist because the committed manifest is one
    reviewable file and a build can drop per-object receipts beside its
    outputs."""
    if p is None:
        return {"kind": "none"}
    if not os.path.exists(p):
        return {"kind": "missing"}
    if os.path.isdir(p):
        return {"kind": "dir", "dir": p}
    v = read_edn_file(p)
    if v is UNREADABLE or not isinstance(v, dict):
        return {"kind": "unreadable"}
    entries = v.get(Kw("objects"))
    return {"kind": "manifest", "entries": entries if entries is not None else v}


def receipt_for(prov: dict, obj: str):
    base = os.path.basename(obj)
    kind = prov["kind"]
    if kind == "dir":
        p = os.path.join(prov["dir"], base + ".edn")
        if os.path.exists(p):
            v = read_edn_file(p)
            return None if v is UNREADABLE else v
        return None
    if kind == "manifest":
        return prov["entries"].get(base)
    return None


def parse_args(args):
    opts = {"objects": []}
    a = list(args)
    while a:
        k = a.pop(0)
        if k == "--link-list":
            opts["link-list"] = a.pop(0) if a else None
        elif k == "--provenance":
            opts["provenance"] = a.pop(0) if a else None
        elif k == "--receipt-out":
            opts["receipt-out"] = a.pop(0) if a else None
        elif k == "--root":
            opts["root"] = a.pop(0) if a else None
        else:
            opts["objects"].append(k)
    return opts


MISSING = object()


def link_entries(opts: dict):
    from_file = None
    if opts.get("link-list") is not None:
        p = opts["link-list"]
        if not os.path.exists(p):
            return MISSING
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return MISSING
        from_file = [ln.strip() for ln in text.splitlines()]
        from_file = [ln for ln in from_file if ln and not ln.startswith("#")]
    return (from_file or []) + opts["objects"]


# ----------------------------------------------------------------- main ----

SELECT_ORDER = ("object", "class", "export", "source", "stub", "sha256", "reason")


def select_keys(r: dict) -> dict:
    """`select-keys` semantics: only keys present on the result, in the
    original's vector order; the class literal is an EDN keyword."""
    out = {}
    for k in SELECT_ORDER:
        if k in r:
            v = r[k]
            out[Kw(k)] = Kw(v) if k == "class" else v
    return out


def main(args) -> None:
    opts = parse_args(args)
    root = os.path.abspath(opts.get("root") or os.getcwd())
    entries = link_entries(opts)
    if entries is MISSING:
        die(2, "UNANSWERED nothing-to-gate reason=link-list-missing path=",
            opts.get("link-list"))
    if not entries:
        die(2, "UNANSWERED nothing-to-gate reason=empty-link-list")
    prov = load_provenance(opts.get("provenance"))
    if prov["kind"] in ("missing", "unreadable"):
        die(2, "UNANSWERED nothing-to-gate reason=provenance-" + prov["kind"],
            "path=", opts.get("provenance"))
    resolved = [os.path.abspath(os.path.join(root, e)) for e in entries]
    absent = [p for p in resolved if not os.path.exists(p)]
    if absent:
        die(2, "UNANSWERED could-not-answer reason=link-input-absent n=",
            len(absent), "first=", absent[0])

    results = []
    for p in resolved:
        buf = read_bytes(p)
        rel = os.path.relpath(p, root)
        if buf is None:
            results.append({"object": rel, "reason": "not-elf"})
        else:
            results.append({"object": rel,
                            **classify(p, buf, receipt_for(prov, p), root)})

    refused = [r for r in results if r.get("reason")]
    foreign = [r for r in refused if r["reason"] in FOREIGN_REASONS]
    unattested = [r for r in refused if r["reason"] in UNATTESTED_REASONS]
    kotoba = [r for r in results if r.get("class") == "kotoba-object"]
    stubs = [r for r in results if r.get("class") == "toolchain-stub"]
    c_sources = []
    for r in foreign:
        for c in r.get("c-sources") or []:
            if c not in c_sources:
                c_sources.append(c)
    imports = []
    for r in results:
        for i in r.get("imports") or []:
            if i not in imports:
                imports.append(i)
    histogram = {}
    for r in refused:
        histogram[r["reason"]] = histogram.get(r["reason"], 0) + 1

    receipt = {
        Kw("format"): Kw("aiueos.k16-pure-native-receipt/v1"),
        Kw("target"): TARGET,
        Kw("link-list"): opts.get("link-list"),
        Kw("provenance"): opts.get("provenance"),
        Kw("scanned"): len(results),
        Kw("kotoba"): len(kotoba),
        Kw("stubs"): len(stubs),
        Kw("refused"): len(refused),
        Kw("foreign"): len(foreign),
        Kw("unattested"): len(unattested),
        Kw("foreign-objects"): [r["object"] for r in foreign],
        Kw("unattested-objects"): [r["object"] for r in unattested],
        Kw("c-sources"): c_sources,
        Kw("reasons"): dict(histogram),
        Kw("objects"): [select_keys(r) for r in results],
        Kw("foreign-code-receipt"): {
            Kw("c-sources"): c_sources,
            Kw("foreign-objects"): [r["object"] for r in foreign],
            Kw("imports"): imports,
            Kw("dynamic-dependencies"): []},
    }

    for r in refused:
        if r["reason"] not in REASONS:
            die(2, "UNANSWERED could-not-answer reason=unknown-reason-literal literal=",
                r["reason"])
        print(("REFUSED foreign-code: " if r["reason"] in FOREIGN_REASONS
               else "REFUSED unattested-provenance: ")
              + r["object"] + " reason=" + r["reason"])
    print("SCANNED\t" + str(len(results)))
    if opts.get("receipt-out"):
        out_path = os.path.join(root, opts["receipt-out"])
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(pr_str(receipt) + "\n")
    if not refused:
        print("AIUEOS_K16_PURE_NATIVE_OK scanned=" + str(len(results))
              + " kotoba=" + str(len(kotoba)) + " stubs=" + str(len(stubs))
              + " foreign=0 unattested=0")
        sys.exit(0)
    print("AIUEOS_K16_PURE_NATIVE_REFUSED scanned=" + str(len(results))
          + " kotoba=" + str(len(kotoba)) + " stubs=" + str(len(stubs))
          + " foreign=" + str(len(foreign))
          + " unattested=" + str(len(unattested)))
    sys.exit(3)


if __name__ == "__main__":
    main(sys.argv[1:])
