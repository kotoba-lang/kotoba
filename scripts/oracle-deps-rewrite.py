#!/usr/bin/env python3
"""oracle-deps-rewrite.py — redirect deleted kotoba-lang repo pins at the kotoba monorepo.

Usage:
  oracle-deps-rewrite.py [--sha SHA] --kotoba-repo PATH <deps.edn>
  oracle-deps-rewrite.py --check <deps.edn>

Rewrite mode (default): every git pin in <deps.edn> that names a deleted
kotoba-lang repo is redirected to the single monorepo pin, keeping the lib
NAME and changing only :git/url / :git/sha / :deps/root:

    <name as-is> {:git/url "https://github.com/kotoba-lang/kotoba"
                  :git/sha "<SHA>" :deps/root "lib/<root>"}

A pin is rewritten when its coordinate is dead: a :git/url at
github.com/kotoba-lang/<name> with <name> not in {kotoba, amu}, a bare
:git/sha or :sha (whose default URL is a deleted repo), or — only for
artifacts named via --rewrite-local-roots — a :local/root sibling pin.
Monorepo-URL pins at an older sha are normalized to --sha (single sha);
extern-sha pins that resolve (e.g. kotoba-core-contracts@b94158f, alive)
are left alone. amu itself is never touched (frozen).

Two gitlibs checkouts of the same repo+sha cannot share :local/root libs
("No known ancestor relationship between local versions"), so every alias
whose basis holds 2+ monorepo checkouts (:test, and every alias pulling amu)
gets an :override-deps entry pinning its whole reachable closure to the same
sha — one git coordinate per lib. The closure is walked at run time from the
monorepo at --sha (lib/catalog.edn + lib/*/deps.edn), never from a
hand-maintained table. Top-level :deps and top-level :override-deps do not
survive an alias with :replace-deps (verified with the Clojure CLI), hence
alias level. Existing :override-deps maps are merged, not replaced.

--check mode changes nothing and exits 1 when any dead kotoba-lang repo URL
or any bare :git/sha/:sha on a kotoba-lang/gftd lib (except amu) remains;
it needs no monorepo and is CI-safe. Suitable as a ci.yml oracle-job step
(run:, no new actions/permissions/secrets).

Metadata source for rewrite mode: --kotoba-repo PATH, either a kotoba git
checkout (uses `git -C PATH show SHA:lib/...`) or a plain directory tree
with lib/catalog.edn + lib/*/deps.edn (used by the fixture tests).
Prepare a small metadata view with e.g.:
  git clone --filter=blob:none --depth 1 --no-checkout URL kotoba-meta
  git -C kotoba-meta fetch --depth 1 origin <SHA>

Exit codes: 0 = rewritten (or check clean); 1 = --check found problems;
2 = rewrite had nothing to do (idempotent); 3 = usage/error (input left
untouched — the file is only replaced atomically at the very end).

The only extern-sha upgrade is documented in EXTRA_OSAHO_LIBS/EXPECT:
any walked lib pinning osaho at a monorepo-URL sha other than --sha (e.g.
shitsuke or jp-go-digital-design-system pinning osaho@b94158f, whose own
graph names deleted kotoba-core-contracts.git via a bare sha, unresolvable)
must match the documented pin exactly, else the script exits loudly;
osaho/kotoba-hir/security are then walked at the single sha like everything
else. Extern pins that resolve (e.g. kotoba-core-contracts@b94158f, alive)
are left alone.
"""
import argparse
import difflib
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_SHA = "ee75001ee44a9b793602d1549e5e977c4562a5fe"
MONO_URL = "https://github.com/kotoba-lang/kotoba"
AMU_LIBS = ("io.github.kotoba-lang/amu", "kotoba-lang/amu")
GROUPS = r"(?:io\.github\.kotoba-lang|kotoba-lang|gftd)"

# EDN treats commas as whitespace: any gap between two tokens may hold commas
# (",", ",,", ",\n", ...). Use EDN_REQ/EDN_OPT for every gap between tokens.
# EDN_REQ/EDN_OPT are applied to comment-stripped text (see _coord_text).
# Searches over raw text that may span a ;-comment either strip first or
# cross the gap procedurally with skip_gap (linear, no regex backtracking).
EDN_REQ = r"[\s,]+"
EDN_OPT = r"[\s,]*"

# Documented extern-sha upgrade: osaho pinned off-sha (monorepo URL) by any
# walked lib (shitsuke, jp-go-digital-design-system, ...). That extern
# revision's own graph names the deleted kotoba-lang/kotoba-core-contracts.git
# via a bare sha, so any basis containing it cannot resolve; osaho at the
# pinned sha is clean. A mismatch with the documented pin exits loudly.
EXTRA_OSAHO_LIBS = ["io.github.kotoba-lang/osaho",
                    "io.github.kotoba-lang/kotoba-hir",
                    "io.github.kotoba-lang/security"]
EXTRA_OSAHO_EXPECT = {"url": MONO_URL + ".git",
                      "sha": "b94158fd48ec541b70d3c455912a06f407537ddc",
                      "root": "lib/kotoba.osaho"}

# Artifacts that also appear under the gftd/ group: emit the override under
# both groups (the unused one is inert). Determined per run from the target
# file: any artifact referenced as gftd/<art> is dual-emitted.


def _git_env():
    env = dict(os.environ)
    # abort stalled on-demand blob fetches instead of hanging forever;
    # the caller retries the whole run (fetched objects stay cached).
    env.setdefault("GIT_HTTP_LOW_SPEED_LIMIT", "1000")
    env.setdefault("GIT_HTTP_LOW_SPEED_TIME", "60")
    return env


def _read_tree_file(repo, sha, path):
    """Read lib/catalog.edn or lib/<x>/deps.edn from a git checkout or dir tree."""
    if os.path.isdir(os.path.join(repo, ".git")):
        r = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (sha, path)],
                           capture_output=True, text=True, env=_git_env())
        if r.returncode != 0:
            return None
        return r.stdout
    try:
        with open(os.path.join(repo, path)) as f:
            return f.read()
    except OSError:
        return None


def load_metadata(repo, sha):
    """Returns (alias_to_path, lib_deps, lib_text, resolve)."""
    cat = _read_tree_file(repo, sha, "lib/catalog.edn")
    if cat is None:
        sys.exit("error: cannot read lib/catalog.edn at %s from %s" % (sha, repo))
    alias_to_path = {}
    # Judge comment-stripped text (offsets are stable) so ;-comments between
    # tokens never hide an entry; resolution values live in "..." strings.
    cat = _strip_comments(cat)
    id_starts = [m.start() for m in re.finditer(r"\{:id" + EDN_REQ, cat)]
    for i, start in enumerate(id_starts):
        # entry ends at the next "{:id " or EOF; entries contain no nested maps
        entry = cat[start:id_starts[i + 1] if i + 1 < len(id_starts) else len(cat)]
        pm = re.search(r':path' + EDN_REQ + r'"(lib/[^"]+)"', entry)
        if not pm:
            continue
        for a in re.findall(r'"((?:io\.github\.kotoba-lang|kotoba-lang|gftd)/[^"]+)"', entry):
            alias_to_path[a] = pm.group(1)

    lib_local_deps = {}  # path -> ([local lib names], [(lib, url, sha, root)] git edges)
    lib_texts = {}  # path -> raw deps.edn text (for pin inspection)

    def lib_deps(path):
        if path in lib_local_deps:
            return lib_local_deps[path]
        txt = _read_tree_file(repo, sha, path + "/deps.edn")
        if txt is None:
            lib_local_deps[path] = None
            return None
        lib_texts[path] = txt
        refs, gits = [], []
        for lib, block in iter_lib_maps(txt):
            eff = _coord_text(block)
            if ":local/root" in eff:
                refs.append(lib)
                continue
            um = re.search(r':git/url' + EDN_REQ + r'"([^"]+)"', eff)
            sm = re.search(r":git/sha" + EDN_REQ + r"\"([0-9a-f]+)\"|:sha" + EDN_REQ + r"\"([0-9a-f]+)\"", eff)
            rm = re.search(r':deps/root' + EDN_REQ + r'"([^"]+)"', eff)
            if um and sm:
                gits.append((lib, um.group(1), sm.group(1) or sm.group(2),
                             rm.group(1) if rm else ""))
        lib_local_deps[path] = (refs, gits)
        return lib_local_deps[path]

    def lib_text(path):
        lib_deps(path)
        return lib_texts.get(path, "")

    def referrer_path(lib):
        """lib/<dir> for lib from an already-read referrer's :local/root edge.

        Covers stale names the catalog no longer claims (e.g. a lib renamed
        to another path): the monorepo itself spells the current path.
        Returns None when no referrer names it or the dir does not exist.
        """
        cands = []
        for txt in lib_texts.values():
            for m in re.finditer(re.escape(lib) + r"(?![a-zA-Z0-9_.\-/])", txt):
                if _in_comment(txt, m.start()) or _in_string(txt, m.start()):
                    continue
                j = skip_gap(txt, m.end())
                if j < len(txt) and txt[j] == "{":
                    k = find_matching_brace(txt, j)
                    rm = re.search(r':local/root' + EDN_REQ + r'"\.\./([a-zA-Z0-9_.\-]+)"',
                                   _strip_comments(txt[j:k]))
                    if rm:
                        cands.append("lib/" + rm.group(1))
        for cand in dict.fromkeys(cands):
            if _read_tree_file(repo, sha, cand + "/deps.edn") is not None:
                return cand
        return None

    def resolve(name):
        """Monorepo :deps/root for a lib name or bare artifact; loud error when unmappable."""
        groups = ("io.github.kotoba-lang/", "kotoba-lang/", "gftd/")
        arts = (name.split("/", 1)[1],) if "/" in name else (name,)
        cands = []
        for art in arts:
            cands.extend([g + art for g in groups])
        if "/" in name:
            cands.append(name)
        for cand in dict.fromkeys(cands):
            if cand in alias_to_path:
                return alias_to_path[cand]
        for cand in dict.fromkeys(cands):
            got = referrer_path(cand)
            if got is not None:
                return got
        sys.exit("error: no monorepo path for %s "
                 "(catalog has no alias and no referrer :local/root names it; "
                 "needs an owner mapping)" % name)

    return alias_to_path, lib_deps, lib_text, resolve


def closure_libs(tops, resolve, lib_deps, sha, dual_arts, present_keys):
    """Fixpoint reachable lib-name set, seeded with the tops under every
    group spelling the target file uses (io.github form always, plus any
    kotoba-lang/ or gftd/ spellings present), so override keys match the
    graph's lib identities exactly. Plus dual-group extras.

    Extern-sha osaho upgrade (documented): any walked lib pinning osaho at a
    monorepo-URL sha other than the target must match EXTRA_OSAHO_EXPECT
    exactly (else loud failure); osaho/kotoba-hir/security are then added
    at the single sha and walked too.
    """
    out, agenda, seen = set(), list(tops), set()
    for art in tops:
        out.add("io.github.kotoba-lang/" + art)
        for key in present_keys.get(art, ()):
            out.add(key)
    upgraded = False
    while agenda:
        art = agenda.pop()
        if art in seen:
            continue
        seen.add(art)
        path = resolve(art)
        got = lib_deps(path)
        if got is None:
            sys.exit("error: cannot read %s/deps.edn at the pinned sha" % path)
        members, gits = got
        for lib in members:
            if lib not in out:
                out.add(lib)
                agenda.append(lib.split("/", 1)[1])
        for (lib, url, gsha, groot) in gits:
            if lib == "io.github.kotoba-lang/osaho" and gsha != sha and not upgraded:
                exp = EXTRA_OSAHO_EXPECT
                if (url, gsha, groot) != (exp["url"], exp["sha"], exp["root"]):
                    sys.exit("error: extern osaho pin changed to %s@%s (%s); "
                             "documented upgrade no longer applies, re-examine"
                             % (url, gsha[:7], groot))
                for elib in EXTRA_OSAHO_LIBS:
                    if elib not in out:
                        out.add(elib)
                        agenda.append(elib.split("/", 1)[1])
                upgraded = True
    for lib in sorted(out):
        grp, art = lib.split("/", 1)
        if art in dual_arts and grp != "gftd":
            out.add("gftd/" + art)
    return out


def dead_url(block):
    """github.com/kotoba-lang/<name> URL with <name> not in {kotoba(.git), amu(.git)}.

    Judges _coord_text(block) (comments blanked), exactly like --check.
    """
    eff = _coord_text(block)
    m = re.search(r":git/url" + EDN_REQ + r"\"https://github\.com/kotoba-lang/([a-zA-Z0-9_.\-]+?)(\.git)?\"",
                  eff)
    if not m:
        return False
    return m.group(1) not in ("kotoba", "amu")


def bare_git_sha(block):
    """:git/sha or :sha without any :git/url (default URL points at a deleted repo).

    Judges _coord_text(block) (comments blanked), exactly like --check: a
    :git/url living only inside a ;-comment does not satisfy a live sha.
    """
    eff = _coord_text(block)
    if ":git/url" in eff:
        return False
    return bool(re.search(r":git/sha" + EDN_REQ + r"\"[0-9a-f]+\"|:sha" + EDN_REQ + r"\"[0-9a-f]+\"", eff))


def has_local_root(block):
    """:local/root present outside strings/comments (same _coord_text basis)."""
    return ":local/root" in _coord_text(block)


def is_canonical(block, root, sha):
    """Monorepo pin judged on _coord_text(block), exactly like --check."""
    eff = _coord_text(block)
    return MONO_URL in eff and sha in eff and root in eff


LIB_KEY = re.compile(r"(?<![a-zA-Z0-9_.\-/])(" + GROUPS + r"/[a-zA-Z0-9_.\-]+)")

def _in_comment(text, pos):
    """True when pos lies inside a ;-comment (string-aware, same-line scan)."""
    ls = text.rfind("\n", 0, pos) + 1
    in_str, esc, i = False, False, ls
    while i < pos:
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
                return True
        i += 1
    return False


def _in_string(text, pos):
    """True when pos lies inside a "..." literal (comment-aware scan)."""
    in_str, esc, i = False, False, 0
    while i < pos:
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            i += 1
        elif c == ';':
            while i < pos and text[i] != '\n':
                i += 1
        else:
            i += 1
    return in_str


def _coord_text(block):
    """Effective coordinate text: ;-comments blanked, offsets stable.

    Single source of truth for coordinate classification: dead_url(),
    bare_git_sha(), has_local_root() and is_canonical() all judge this
    text, so --check and the rewrite pass can never disagree on what a
    pin's coordinates are. "..." strings (and hence the URL/sha/root
    values) pass through byte-identical.
    """
    return _strip_comments(block)


def _find_map_open(text, key_end):
    """Brace index for `key {...}` across a comment+comma gap, else None."""
    j = skip_gap(text, key_end)
    if j < len(text) and text[j] == "{":
        return j
    return None


def _strip_comments(text):
    """Blank ;-comments (newlines kept, offsets stable); strings aware."""
    out = []
    i, n, in_str, esc = 0, len(text), False, False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
        else:
            if c == '"':
                in_str = True
                out.append(c)
                i += 1
            elif c == ';':
                while i < n and text[i] != '\n':
                    out.append(' ')
                    i += 1
            else:
                out.append(c)
                i += 1
    return "".join(out)


def skip_gap(txt, i):
    """Skip EDN whitespace (incl. commas) and ;-comments; linear, no backtracking."""
    n = len(txt)
    while i < n:
        c = txt[i]
        if c in " \t\r\n,":
            i += 1
        elif c == ";":
            while i < n and txt[i] != "\n":
                i += 1
        else:
            break
    return i


def iter_lib_maps(txt):
    """Yield (key, flat map block) for each `GROUP/name {...}` pin.

    Comment-tolerant gap between key and map; linear scan (a nested
    `(?:\\s+|;...)+` regex backtracks catastrophically on comment-heavy
    monorepo files, so the gap is skipped procedurally). Raises ValueError
    on unbalanced braces via find_matching_brace.
    """
    for m in LIB_KEY.finditer(txt):
        if _in_comment(txt, m.start()) or _in_string(txt, m.start()):
            continue
        key = m.group(1)
        e = m.end()
        if e < len(txt) and (txt[e].isalnum() or txt[e] in "_.-/"):
            continue
        j = _find_map_open(txt, e)
        if j is not None:
            yield key, txt[j:find_matching_brace(txt, j)]


def iter_lib_spans(text):
    """Like iter_lib_maps but yields (key, start, end, block) with offsets."""
    for m in LIB_KEY.finditer(text):
        if _in_comment(text, m.start()) or _in_string(text, m.start()):
            continue
        key = m.group(1)
        e = m.end()
        if e < len(text) and (text[e].isalnum() or text[e] in "_.-/"):
            continue
        j = _find_map_open(text, e)
        if j is not None:
            k = find_matching_brace(text, j)
            yield key, m.start(), k, text[j:k]


def rewrite_direct(text, resolve, sha, rewrite_locals):
    """Pass 1: rewrite dead pins. Returns (text, [rewritten artifacts]).

    Only io.github.kotoba-lang|kotoba-lang|gftd groups are scanned.
    cognitect test-runner's bare :git/tag+:git/sha uses another group
    and never reaches here, so every bare sha here defaults to a deleted
    kotoba-lang repo.
    """
    changed = []
    return _rewrite_direct_acc(text, resolve, sha, rewrite_locals, changed)


def _rewrite_direct_acc(text, resolve, sha, rewrite_locals, changed):
    for key, start, end, block in iter_lib_spans(text):
        if key in AMU_LIBS:
            continue  # amu is frozen
        grp, art = key.split("/", 1)
        # Same _coord_text basis as --check (dead_url/bare_git_sha/
        # has_local_root/is_canonical all strip internally); a MONO_URL or
        # sha living only in a ;-comment never counts either way.
        eff = _coord_text(block)
        needs = (dead_url(block) or bare_git_sha(block) or
                 (has_local_root(block) and art in rewrite_locals) or
                 (MONO_URL in eff and sha not in eff))
        if not needs:
            continue
        root = resolve(key)
        if is_canonical(block, root, sha):
            continue
        new = (key + "\n        {:git/url \"%s\"\n"
               "         :git/sha \"%s\"\n"
               "         :deps/root \"%s\"}") % (MONO_URL, sha, root)
        changed.append(art)
        return _rewrite_direct_acc(text[:start] + new + text[end:],
                                   resolve, sha, rewrite_locals, changed)
    return text, changed


def check_balanced(text):
    """Whole-file bracket balance (strings/comments aware); raises ValueError."""
    stack, in_str, esc, line = [], False, False, 1
    closes = {")": "(", "]": "[", "}": "{"}
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
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
            elif c in "([{":
                stack.append((c, line))
            elif c in ")]}":
                if not stack or stack[-1][0] != closes[c]:
                    raise ValueError("unbalanced %r at line %d" % (c, line))
                stack.pop()
        i += 1
    if in_str:
        raise ValueError("unterminated string")
    if stack:
        raise ValueError("unclosed %r opened at line %d" % (stack[-1][0], stack[-1][1]))


def find_matching_brace(text, open_idx):
    """Index just past the brace matching text[open_idx]; strings/comments aware."""
    i, depth, in_str, esc, n = open_idx, 0, False, False, len(text)
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
    """[(name, body_open, body_close)] for each map-valued alias in :aliases.

    The :aliases -> { gap is comment+comma transparent (skip_gap), and an
    :aliases occurrence inside a ;-comment or "..." string is skipped.
    """
    a_open = None
    for m in re.finditer(
            r"(?<![a-zA-Z0-9_.\-/+*!?<>:#]):aliases(?![a-zA-Z0-9_.\-/+*!?<>])",
            text):
        if _in_comment(text, m.start()) or _in_string(text, m.start()):
            continue
        j = _find_map_open(text, m.end())
        if j is not None:
            a_open = j
            break
    if a_open is None:
        return []
    a_close = find_matching_brace(text, a_open)
    bodies, i, n = [], a_open + 1, a_close - 1
    while i < n:
        km = re.match(r"[\s,;]*(;[^\n]*[\s,]*)?(:[A-Za-z0-9_.\-/+*!?<>]+)", text[i:n])
        if not km:
            i += 1
            continue
        name, j = km.group(2), i + km.end()
        while j < n and (text[j] in ' \t\r\n,' or text[j] == ';'):
            if text[j] == ';':
                while j < n and text[j] != '\n':
                    j += 1
                continue
            j += 1
        if j < n and text[j] == '{':
            close = find_matching_brace(text, j)
            bodies.append((name, j, close))
            i = close
        else:
            i = j + 1 if j < n else n
    return bodies


def current_tops(text, sha):
    """Artifacts holding monorepo-URL pins at sha (the live basis tops)."""
    tops = set()
    for key, block in iter_lib_maps(text):
        if key in AMU_LIBS:
            continue
        eff = _coord_text(block)
        if MONO_URL in eff and sha in eff:
            tops.add(key.split("/", 1)[1])
    return tops


def find_entry(text, lib):
    """(start, end) of `lib {...}` pin, or None; comment-tolerant gap.

    A lib name occurring only inside a ;-comment is not a live pin, so
    such matches are skipped; the caller then takes the add path, which
    leaves the comment bytes untouched, instead of splicing into them.
    """
    for m in re.finditer(re.escape(lib) + r"(?![a-zA-Z0-9_.\-/])", text):
        if _in_comment(text, m.start()) or _in_string(text, m.start()):
            continue
        j = _find_map_open(text, m.end())
        if j is not None:
            return m.start(), find_matching_brace(text, j)
    return None


def entry_text(lib, root, sha, indent):
    return ("%s%s\n"
            "%s{:git/url \"%s\"\n"
            "%s :git/sha \"%s\"\n"
            "%s :deps/root \"%s\"}") % (
        indent, lib, indent, MONO_URL, indent, sha, indent, root)


def last_entry_indent(map_text):
    lines = map_text.split("\n")
    for ln in reversed(lines):
        if re.match(r"^(?:\s*)(?:io\.github\.kotoba-lang|kotoba-lang|gftd)/", ln):
            return re.match(r"^(\s*)", ln).group(1)
    for ln in reversed(lines[1:-1] if len(lines) > 2 else lines):
        mm = re.match(r"^(\s*)\S", ln)
        if mm:
            return mm.group(1)
    return " " * 39


def ensure_override_in_alias(text, name, b_open, b_close, sha, want, resolve):
    """Merge :override-deps pins for want into this alias body."""
    if not want:
        return text, False
    body = text[b_open:b_close]
    # :override-deps -> { across any whitespace/comma/;-comment gap; a fake
    # :override-deps inside a ;-comment or "..." string is not an entry.
    o_rel = None
    for cand in re.finditer(
            r"(?<![a-zA-Z0-9_.\-/+*!?<>:#]):override-deps(?![a-zA-Z0-9_.\-/+*!?<>])",
            body):
        if _in_comment(body, cand.start()) or _in_string(body, cand.start()):
            continue
        j = _find_map_open(body, cand.end())
        if j is not None:
            o_rel = j
            break
    if o_rel is not None:
        o_open = b_open + o_rel
        o_close = find_matching_brace(text, o_open)
        new_map = text[o_open:o_close]
        merged = []
        for lib in sorted(want):
            art = lib.split("/", 1)[1]
            root = resolve(lib)
            em = find_entry(new_map, lib)
            ins = last_entry_indent(new_map)
            if em:
                eblock = new_map[em[0]:em[1]]
                if is_canonical(eblock, root, sha):
                    continue
                new_map = (new_map[:em[0]] +
                           entry_text(lib, root, sha, ins) + new_map[em[1]:])
                merged.append(art + "(replaced)")
            else:
                entry = "\n" + entry_text(lib, root, sha, ins)
                new_map = new_map[:len(new_map) - 1].rstrip("\n") + entry + "}"
                merged.append(art + "(added)")
        if not merged:
            return text, False
        return text[:o_open] + new_map + text[o_close:], True
    inner = text[b_open:b_close]
    key_indent = None
    for mm in re.finditer(r"\n([ ]+):(extra-deps|replace-deps|main-opts|exec-fn|extra-paths|jvm-opts)\b",
                          inner):
        key_indent = mm.group(1)
    if key_indent is None:
        key_indent = " " * 14
    mi = key_indent + " " * len(":override-deps {")
    roots = {lib.split("/", 1)[1]: resolve(lib) for lib in want}
    lines = [entry_text(lib, roots[lib.split("/", 1)[1]], sha, mi) for lib in sorted(want)]
    block = "\n%s:override-deps {%s\n%s}" % (
        key_indent, "".join("\n" + e for e in lines), key_indent)
    head = text[:b_close - 1].rstrip("\n")
    return head + block + "}" + text[b_close:], True


def present_groups(text):
    """artifact -> {full lib keys used in the file} for kotoba-lang/gftd groups."""
    out = {}
    for key, _block in iter_lib_maps(text):
        if key in AMU_LIBS:
            continue
        out.setdefault(key.split("/", 1)[1], set()).add(key)
    return out


def rewrite_aliases(text, tops, resolve, lib_deps, dual_arts, sha):
    present = present_groups(text)
    changed = []
    guard = 0
    while guard < 60:
        guard += 1
        bodies = alias_bodies(text)
        progressed = False
        for name, b_open, b_close in bodies:
            body = text[b_open:b_close]
            # Judge comment-stripped body (offsets unused here): ;-comments
            # between :replace-deps and { (or amu and {) are transparent, and
            # fake keys living only in comments never match.
            sbody = _strip_comments(body)
            if name == ":test" and re.search(r":replace-deps" + EDN_OPT + r"\{", sbody):
                continue
            amu = bool(re.search(r"kotoba-lang/amu" + EDN_OPT + r"\{[^{}]*(:git/url|:git/sha)",
                                 sbody))
            if name != ":test" and not amu:
                continue
            sub = set()
            if name == ":test":
                sub.update(tops)
            if amu:
                sub.update(["security", "kotoba-script"])
            if not sub:
                continue
            subwant = closure_libs(sub, resolve, lib_deps, sha,
                                   dual_arts, present)
            new_text, ch = ensure_override_in_alias(text, name, b_open, b_close,
                                                    sha, subwant, resolve)
            if ch:
                text = new_text
                changed.append(name)
                progressed = True
                break
        if not progressed:
            break
    return text, changed


def check_file(path):
    """Exit 1 with a listing when dead pins remain; 0 when clean. No writes."""
    with open(path) as f:
        text = f.read()
    # scan comment-stripped text so ;-comments never count and a :git/url
    # value on the next line still matches; offsets map 1:1 to text.
    stripped = _strip_comments(text)
    problems = []
    for m in re.finditer(
            r":git/url" + EDN_REQ + r"\"(https://github\.com/kotoba-lang/([a-zA-Z0-9_.\-]+?)(\.git)?)\"",
            stripped):
        if m.group(2) not in ("kotoba", "amu"):
            lineno = stripped.count("\n", 0, m.start()) + 1
            problems.append("%d: dead repo URL %s" % (lineno, m.group(1)))
    try:
        # Same span enumeration as the rewrite pass (iter_lib_spans), so both
        # modes see the same pins at the same offsets.
        lib_spans = list(iter_lib_spans(text))
    except ValueError as e:
        problems.append("unbalanced EDN: %s" % e)
        lib_spans = []
    for key, start, _end, block in lib_spans:
        if key in AMU_LIBS:
            continue
        # Judge effective (non-comment) coordinates only: a :git/url that
        # lives inside a ;-comment does not satisfy a live :git/sha.
        eff = _coord_text(block)
        if ":git/url" not in eff and re.search(
                r":git/sha" + EDN_REQ + r"\"[0-9a-f]+\"|:sha" + EDN_REQ + r"\"[0-9a-f]+\"", eff):
            lineno = text.count("\n", 0, start) + 1
            problems.append("%d: bare git sha without :git/url: %s" % (lineno, key))
    if problems:
        print("check failed (%s):" % path)
        for p in problems:
            print("  " + p)
        return 1
    print("check clean: %s" % path)
    return 0


def atomic_write(path, data):
    tmp = tempfile.NamedTemporaryFile(mode="w", dir=os.path.dirname(path) or ".",
                                      prefix=".oracle-deps-", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        os.replace(tmp.name, path)
    except BaseException:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Redirect deleted kotoba-lang repo pins at the kotoba monorepo.")
    ap.add_argument("deps_edn", help="deps.edn to rewrite or check")
    ap.add_argument("--sha", default=DEFAULT_SHA,
                    help="single monorepo sha (default: %(default)s)")
    ap.add_argument("--kotoba-repo",
                    help="kotoba checkout or dir tree with lib/catalog.edn "
                         "(required for rewrite mode)")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 when dead pins remain")
    ap.add_argument("--rewrite-local-roots", default="",
                    help="comma-separated artifacts whose :local/root sibling "
                         "pins are dead layout and must be rewritten too")
    args = ap.parse_args(argv)

    if args.check:
        return check_file(args.deps_edn)

    if not args.kotoba_repo:
        ap.error("--kotoba-repo is required for rewrite mode")
    try:
        with open(args.deps_edn) as f:
            text = f.read()
    except OSError as e:
        print("error: cannot read %s: %s" % (args.deps_edn, e))
        return 3
    _alias_to_path, lib_deps, _lib_text, resolve = load_metadata(args.kotoba_repo,
                                                              args.sha)
    try:
        check_balanced(text)
        new_text, direct = rewrite_direct(text, resolve, args.sha,
                                          set(a for a in args.rewrite_local_roots.split(",")
                                              if a))
        # tops after pass 1: freshly rewritten pins count too
        tops = current_tops(new_text, args.sha)
        # Live gftd/ pins only: a gftd/... mention inside a ;-comment or
        # "..." string is not a pin the rewrite pass sees.
        dual_arts = set()
        for gm in re.finditer(r"gftd/[a-zA-Z0-9_.\-]+", new_text):
            if _in_comment(new_text, gm.start()) or _in_string(new_text, gm.start()):
                continue
            dual_arts.add(gm.group(0).split("/", 1)[1])
        new_text, aliases = rewrite_aliases(new_text, tops, resolve,
                                            lib_deps, dual_arts, args.sha)
    except ValueError as e:
        print("error: %s (input left untouched)" % e)
        return 3
    except SystemExit as e:
        # load_metadata / closure loud errors already printed
        if isinstance(e.code, str):
            print(e.code)
        return 3
    if not direct and not aliases:
        print("no rewritable entries found")
        return 2
    diff = "".join(difflib.unified_diff(
        text.splitlines(keepends=True), new_text.splitlines(keepends=True),
        fromfile=args.deps_edn, tofile=args.deps_edn))
    print(diff, end="")
    atomic_write(args.deps_edn, new_text)
    print("rewrote direct: %s; override in aliases: %s" %
          (",".join(sorted(set(direct))) if direct else "-",
           ",".join(sorted(set(aliases))) if aliases else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
