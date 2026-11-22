#!/usr/bin/env python3
"""rewrite-oracle-deps.py — redirect deleted kotoba-lang repo pins to the kotoba monorepo.

Usage: rewrite-oracle-deps.py <deps.edn path>

Does two things, both format-preserving (comments and unrelated entries untouched):

1. Direct entries: every `io.github.kotoba-lang/<name>` (also `kotoba-lang/<name>`
   and `gftd/<name>`) entry for a migrated lib whose coordinate still names a
   deleted repo (a `:git/url` at github.com/kotoba-lang, a bare `:git/sha`, or a
   bare `:sha`) is rewritten to the single monorepo pin, keeping the lib NAME:

       <name as-is> {:git/url "https://github.com/kotoba-lang/kotoba"
                     :git/sha "<SHA>" :deps/root "lib/<root>"}

   Entries already at that pin, and `:local/root` / `:mvn` entries, are untouched.

2. Closure override: one monorepo git pin per lib NAME means one gitlibs
   checkout per name, and the monorepo's libs reference each other via
   `:local/root`. When two checkouts of the same repo+sha coexist in one basis,
   a lib reachable through both (e.g. error via security and kotoba-script)
   fails resolution ("No known ancestor relationship between local versions").
   A top-level (or alias-level) git pin wins over those transitive locals, so
   every alias whose basis holds 2+ monorepo checkouts gets an `:override-deps`
   entry pinning the WHOLE reachable closure to the same monorepo pin — one
   git coordinate per lib collapses every cross-reference to a single checkout.
   Alias level (not top level): top-level :deps and top-level :override-deps
   are both dropped under an alias with :replace-deps (verified empirically
   with the Clojure CLI), while alias-level :override-deps applies.
   Amu-carrying aliases redirect amu's dead security/kotoba-script pins the
   same way (amu itself stays frozen). Existing :override-deps maps are merged,
   not replaced. Only aliases relevant to CI bases are touched: every alias
   that pulls amu, plus the `:test` alias.

Lib->root table is proven by lib/catalog.edn at the pinned sha
(:aliases entries). CLOSURE lists the transitive monorepo-local reachable set
per top artifact, walked from the monorepo at the pinned sha (same source).
Single SHA for every monorepo pin.

Exit 0 = changed (prints what), 2 = nothing to do.
"""
import re
import sys

SHA = "ee75001ee44a9b793602d1549e5e977c4562a5fe"
URL = "https://github.com/kotoba-lang/kotoba"

# artifact -> monorepo :deps/root (catalog.edn :aliases at SHA above)
TABLE = {
    "test": "lib/kotoba.test",
    "io": "lib/kotoba.io",
    "pprint": "lib/kotoba.pprint",
    "bytes": "lib/kotoba.bytes",
    "security": "lib/kotoba.security",
    "text": "lib/kotoba.text",
    "edn": "lib/kotoba.edn",
    "image": "lib/kotoba.image",
    "process": "lib/kotoba.process",
    "json": "lib/kotoba.json",
    "nagare": "lib/kotoba.nagare",
    "kami-engine-cae-solver": "lib/kotoba.kamiEngineCaeSolver",
    "org-vrmc-vrm": "lib/org.vrmC.vrm",
    "character": "lib/kotoba.character",
    "kami-engine-sdk": "lib/kotoba.kamiEngineSdk",
    "kami-mangaka-render": "lib/kotoba.kamiMangakaRender",
    "kami-mangaka-page": "lib/kotoba.kamiMangakaPage",
    "kotoba-script": "lib/kotoba.kotobaScript",
}

# artifact -> monorepo :deps/root for every lib reachable inside the closures
# (catalog.edn at SHA; glb is the stale name used by org.vrmC.vrm's deps.edn
# for the lib at lib/org.khronos.glb).
ROOTS = {
    "bytes": "lib/kotoba.bytes",
    "character": "lib/kotoba.character",
    "coll": "lib/kotoba.coll",
    "edn": "lib/kotoba.edn",
    "error": "lib/kotoba.error",
    "glb": "lib/org.khronos.glb",
    "html": "lib/kotoba.html",
    "i18n": "lib/kotoba.i18n",
    "image": "lib/kotoba.image",
    "io": "lib/kotoba.io",
    "io-multiformats": "lib/kotoba.ioMultiformats",
    "json": "lib/kotoba.json",
    "kami-engine-cae-solver": "lib/kotoba.kamiEngineCaeSolver",
    "kami-engine-sdk": "lib/kotoba.kamiEngineSdk",
    "kami-mangaka-page": "lib/kotoba.kamiMangakaPage",
    "kami-mangaka-render": "lib/kotoba.kamiMangakaRender",
    "kami-mangaka-text": "lib/kotoba.kamiMangakaText",
    "kotoba-script": "lib/kotoba.kotobaScript",
    "nagare": "lib/kotoba.nagare",
    "osaho": "lib/kotoba.osaho",
    "kotoba-hir": "lib/kotoba.kotobaHir",
    "org-ietf-cbor": "lib/org.ietf.cbor",
    "org-ietf-deflate": "lib/org.ietf.deflate",
    "org-ietf-ed25519": "lib/org.ietf.ed25519",
    "org-ietf-x25519": "lib/org.ietf.x25519",
    "org-nist-sha2": "lib/gov.nist.sha2",
    "org-vrmc-vrm": "lib/org.vrmC.vrm",
    "org-w3-png": "lib/org.w3.png",
    "physics": "lib/kotoba.physics",
    "pprint": "lib/kotoba.pprint",
    "process": "lib/kotoba.process",
    "security": "lib/kotoba.security",
    "set": "lib/kotoba.set",
    "shitsuke": "lib/kotoba.shitsuke",
    "spec": "lib/kotoba.spec",
    "test": "lib/kotoba.test",
    "text": "lib/kotoba.text",
    "walk": "lib/kotoba.walk",
}

GROUPS = r"(?:io\.github\.kotoba-lang|kotoba-lang|gftd)"

# Artifacts that also appear under the gftd/ group: emit the override under
# both groups (the unused one is inert).
DUAL_GROUP = ["kami-engine-sdk", "kami-mangaka-render", "kami-mangaka-page",
              "kami-mangaka-text"]

# Manual closure supplement (extern-sha upgrade).
# lib/kotoba.shitsuke pins io.github.kotoba-lang/osaho at b94158f (monorepo
# URL). That extern revision's own graph names the deleted
# kotoba-lang/kotoba-core-contracts.git repo via a bare :git/sha, so any
# basis containing shitsuke cannot resolve (measured 2026-11-22 on
# hygaccess-plant). osaho at the pinned monorepo sha is clean (all :local/root
# plus alive externals), so shitsuke's closure is extended with osaho,
# kotoba-hir (osaho's local dep) and security (osaho's local dep), all
# redirected to the single sha like everything else. osaho@ee75001's own
# closure beyond these three is already inside the cae-solver closure.
CLOSURE_EXTRA = {
    "kami-engine-cae-solver": ["io.github.kotoba-lang/osaho",
                               "io.github.kotoba-lang/kotoba-hir",
                               "io.github.kotoba-lang/security"],
    # Walked 2026-11-22 from lib/kotoba.osaho and lib/kotoba.kotobaHir
    # deps.edn at the pinned sha (all :local/root, no externals).
    "osaho": ["io.github.kotoba-lang/osaho",
              "io.github.kotoba-lang/error",
              "io.github.kotoba-lang/bytes",
              "io.github.kotoba-lang/io",
              "io.github.kotoba-lang/edn",
              "io.github.kotoba-lang/test",
              "io.github.kotoba-lang/coll",
              "io.github.kotoba-lang/text",
              "io.github.kotoba-lang/kotoba-hir",
              "io.github.kotoba-lang/security",
              "io.github.kotoba-lang/org-nist-sha2",
              "io.github.kotoba-lang/io-multiformats",
              "io.github.kotoba-lang/org-ietf-cbor"],
    "kotoba-hir": ["io.github.kotoba-lang/kotoba-hir",
                   "io.github.kotoba-lang/test",
                   "io.github.kotoba-lang/coll"],
}

# Transitive monorepo-local reachable set per top artifact, walked from
# the monorepo at SHA (closure.py from lib/catalog.edn + lib/*/deps.edn).
CLOSURE = {
    'bytes': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'character': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/character',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'edn': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'image': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/image',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/org-ietf-deflate',
        'io.github.kotoba-lang/org-w3-png',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'io': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'json': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/json',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'kami-engine-cae-solver': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/coll',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/error',
        'io.github.kotoba-lang/html',
        'io.github.kotoba-lang/i18n',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/json',
        'io.github.kotoba-lang/kami-engine-cae-solver',
        'io.github.kotoba-lang/physics',
        'io.github.kotoba-lang/pprint',
        'io.github.kotoba-lang/set',
        'io.github.kotoba-lang/shitsuke',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
        'io.github.kotoba-lang/walk',
    ],
    'kami-engine-sdk': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/coll',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/error',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/json',
        'io.github.kotoba-lang/kami-engine-sdk',
        'io.github.kotoba-lang/set',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
        'io.github.kotoba-lang/walk',
    ],
    'kami-mangaka-page': [
        'gftd/kami-mangaka-text',
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/kami-mangaka-page',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'kami-mangaka-render': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/json',
        'io.github.kotoba-lang/kami-mangaka-render',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'kotoba-script': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/coll',
        'io.github.kotoba-lang/error',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/kotoba-script',
        'io.github.kotoba-lang/set',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
        'io.github.kotoba-lang/walk',
    ],
    'nagare': [
        'io.github.kotoba-lang/nagare',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'org-vrmc-vrm': [
        'io.github.kotoba-lang/glb',
        'io.github.kotoba-lang/org-vrmc-vrm',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'pprint': [
        'io.github.kotoba-lang/pprint',
    ],
    'process': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/process',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'security': [
        'io.github.kotoba-lang/bytes',
        'io.github.kotoba-lang/coll',
        'io.github.kotoba-lang/edn',
        'io.github.kotoba-lang/error',
        'io.github.kotoba-lang/io',
        'io.github.kotoba-lang/io-multiformats',
        'io.github.kotoba-lang/org-ietf-cbor',
        'io.github.kotoba-lang/org-ietf-ed25519',
        'io.github.kotoba-lang/org-ietf-x25519',
        'io.github.kotoba-lang/org-nist-sha2',
        'io.github.kotoba-lang/pprint',
        'io.github.kotoba-lang/security',
        'io.github.kotoba-lang/set',
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
        'io.github.kotoba-lang/walk',
    ],
    'test': [
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
    'text': [
        'io.github.kotoba-lang/spec',
        'io.github.kotoba-lang/test',
        'io.github.kotoba-lang/text',
    ],
}


def is_canonical(block, root):
    return URL in block and SHA in block and root in block


def rewrite_direct(text):
    """Pass 1: rewrite dead direct-entry maps. Returns (text, [names])."""
    changed = []
    for artifact, root in TABLE.items():
        pat = re.compile(
            r"(" + GROUPS + r"/" + re.escape(artifact) + r")"
            r"(\s*\n?\s*)(\{[^{}]*\})")
        def repl(m, artifact=artifact, root=root):
            key, gap, block = m.group(1), m.group(2), m.group(3)
            if is_canonical(block, root):
                return None  # already at target pin
            if not re.search(r":git/url|:git/sha|:sha\b", block):
                return None  # :local/root, :mvn, ... — not a repo pin
            # normalize: key on its own line, canonical map under it
            return (key + "\n        {:git/url \"%s\"\n"
                    "         :git/sha \"%s\"\n"
                    "         :deps/root \"%s\"}") % (URL, SHA, root)
        # manual loop (need per-match skip)
        out = []
        pos = 0
        hit = False
        for m in pat.finditer(text):
            new = repl(m)
            if new is None:
                continue
            out.append(text[pos:m.start()])
            out.append(new)
            pos = m.end()
            hit = True
        if hit:
            out.append(text[pos:])
            text = "".join(out)
            changed.append(artifact)
    return text, changed


def find_matching_brace(text, open_idx):
    """Given index of '{', return index just past the matching '}' (strings/comments aware)."""
    i = open_idx
    depth = 0
    in_str = False
    esc = False
    n = len(text)
    while i < n:
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == ';':
                while i < n and text[i] != '\n':
                    i += 1
                continue
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise ValueError("unbalanced braces from %d" % open_idx)


def alias_bodies(text):
    """Yield (alias_name, body_open_idx, body_close_idx) for each alias in :aliases."""
    m = re.search(r":aliases\s*\{", text)
    if not m:
        return []
    a_open = m.end() - 1
    a_close = find_matching_brace(text, a_open)
    bodies = []
    i = a_open + 1
    n = a_close - 1
    while i < n:
        km = re.match(r"[\s,;]*(;[^\n]*[\s,]*)?(:[A-Za-z0-9_.\-/+*!?<>]+)", text[i:n])
        if not km:
            i += 1
            continue
        name = km.group(2)
        j = i + km.end()
        # skip whitespace/comments to value
        while j < n:
            if text[j] in ' \t\r\n,':
                j += 1
                continue
            if text[j] == ';':
                while j < n and text[j] != '\n':
                    j += 1
                continue
            break
        if j < n and text[j] == '{':
            close = find_matching_brace(text, j)
            bodies.append((name, j, close))
            i = close
        else:
            i = j + 1 if j < n else n
    return bodies


def closure_libs(tops):
    """Fixpoint lib-name set (with groups) over CLOSURE+CLOSURE_EXTRA, plus dual-group extras."""
    full = {t: list(v) for t, v in CLOSURE.items()}
    for t, members in CLOSURE_EXTRA.items():
        have = full.setdefault(t, [])
        have.extend(m for m in members if m not in have)
    out = set()
    agenda = list(tops)
    while agenda:
        t = agenda.pop()
        for lib in full.get(t, []):
            if lib not in out:
                out.add(lib)
                agenda.append(lib.split("/", 1)[1])
    for lib in sorted(out):
        grp, art = lib.split("/", 1)
        if art in DUAL_GROUP and grp != "gftd":
            out.add("gftd/" + art)
    return out


def entry_text(lib, indent):
    grp, art = lib.split("/", 1)
    root = ROOTS[art]
    return ("%s%s\n"
            "%s{:git/url \"%s\"\n"
            "%s :git/sha \"%s\"\n"
            "%s :deps/root \"%s\"}") % (
        indent, lib, indent, URL, indent, SHA, indent, root)


def last_entry_indent(map_text):
    # Prefer lib-key lines (entries we manage); continuation lines like
    # ` :git/sha ...` sit one deeper and would staircase the block.
    lines = map_text.split("\n")
    for ln in reversed(lines):
        mm = re.match(r"^(\s*)(?:io\.github\.kotoba-lang|kotoba-lang|gftd)/", ln)
        if mm:
            return mm.group(1)
    for ln in reversed(lines[1:-1] if len(lines) > 2 else lines):
        mm = re.match(r"^(\s*)\S", ln)
        if mm:
            return mm.group(1)
    return " " * 39


def current_direct_tops(text):
    """TABLE artifacts holding a git pin anywhere (fresh rewrite or already canonical)."""
    tops = set()
    for artifact in TABLE:
        for m in re.finditer(
                GROUPS + r"/" + re.escape(artifact) +
                r"(?![a-zA-Z0-9_.\-/])\s*\n?\s*(\{[^{}]*\})", text):
            if re.search(r":git/url|:git/sha|:sha\b", m.group(1)):
                tops.add(artifact)
                break
    return tops


def alias_tops(name, body, direct_tops):
    """Which top artifacts' closures this alias's basis needs pinned."""
    amu = bool(re.search(r"kotoba-lang/amu\s*\n?\s*\{[^{}]*(:git/url|:git/sha)", body))
    repl = bool(re.search(r":replace-deps\s*\{", body))
    tops = set()
    if amu:
        # amu is frozen; its dead security/kotoba-script pins redirect here
        tops.update(["security", "kotoba-script"])
    # :test (without :replace-deps) sees the top-level direct pins
    if name == ":test" and not repl:
        tops.update(direct_tops)
    return tops


def ensure_override_in_alias(text, name, b_open, b_close, direct_tops):
    """Ensure :override-deps pins the whole closure in this alias body."""
    body = text[b_open:b_close]
    want = closure_libs(alias_tops(name, body, direct_tops))
    if not want:
        return text, False
    om = re.search(r":override-deps\s*\{", body)
    if om:
        o_open = b_open + om.end() - 1
        o_close = find_matching_brace(text, o_open)
        new_map = text[o_open:o_close]
        merged = []
        for lib in sorted(want):
            art = lib.split("/", 1)[1]
            root = ROOTS[art]
            em = re.search(re.escape(lib) + r"\s*\n?\s*\{[^{}]*\}", new_map)
            ins_indent = last_entry_indent(new_map)
            if em:
                if is_canonical(em.group(0), root):
                    continue
                new_map = (new_map[:em.start()] +
                           entry_text(lib, ins_indent) + new_map[em.end():])
                merged.append(art + "(replaced)")
            else:
                entry = "\n" + entry_text(lib, ins_indent)
                new_map = new_map[:len(new_map) - 1].rstrip("\n") + entry + "}"
                merged.append(art + "(added)")
        if not merged:
            return text, False
        text = text[:o_open] + new_map + text[o_close:]
        return text, True
    else:
        inner_text = text[b_open:b_close]
        key_indent = None
        for mm in re.finditer(r"\n([ ]+):(extra-deps|replace-deps|main-opts|exec-fn|extra-paths|jvm-opts)\b", inner_text):
            key_indent = mm.group(1)
        if key_indent is None:
            key_indent = " " * 14
        map_indent = key_indent + " " * len(":override-deps {")
        entry_lines = [entry_text(lib, map_indent) for lib in sorted(want)]
        block = ("\n%s:override-deps {%s\n%s}" % (
            key_indent, "".join("\n" + e for e in entry_lines), key_indent))
        # insert before final '}' of alias body (b_close-1), keeping all file prefix
        head = text[:b_close - 1].rstrip("\n")
        text = head + block + "}" + text[b_close:]
        return text, True


def rewrite_aliases(text, direct):
    changed_aliases = []
    # tops from the CURRENT pins (idempotent: fresh rewrites and re-runs agree)
    direct_tops = set(direct) | current_direct_tops(text)
    # iterate over snapshot of bodies; recompute after each edit (offsets shift)
    guard = 0
    while guard < 40:
        guard += 1
        bodies = alias_bodies(text)
        progressed = False
        for name, b_open, b_close in bodies:
            new_text, changed = ensure_override_in_alias(
                text, name, b_open, b_close, direct_tops)
            if changed:
                text = new_text
                changed_aliases.append(name)
                progressed = True
                break
        if not progressed:
            break
    return text, changed_aliases


def main():
    path = sys.argv[1]
    with open(path) as f:
        text = f.read()
    text, direct = rewrite_direct(text)
    text, aliases = rewrite_aliases(text, direct)
    if not direct and not aliases:
        print("no rewritable entries found")
        return 2
    with open(path, "w") as f:
        f.write(text)
    print("rewrote direct: %s; override in aliases: %s" %
          (",".join(direct) if direct else "-", ",".join(aliases) if aliases else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
