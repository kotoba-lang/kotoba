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
:git/sha or :sha (whose default URL points at a deleted repo), or — only for
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
import subprocess
import sys
import tempfile

DEFAULT_SHA = "ee75001ee44a9b793602d1549e5e977c4562a5fe"
MONO_URL = "https://github.com/kotoba-lang/kotoba"
AMU_LIBS = ("io.github.kotoba-lang/amu", "kotoba-lang/amu")

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


# ---------------------------------------------------------------------------
# Pure-Python EDN lexer + position-span AST (single source of truth).
#
# Standard library only. Whitespace, `,` and `;[^\n]*` comments are trivia
# skipped between tokens. `{`, `}`, `[`, `]`, `(`, `)`, `"`, `;`, whitespace
# and `,` terminate a symbol/keyword immediately, so `:git/url"..."` lexes
# as a keyword token followed by a string token with no gap required.
# Every node keeps its (start, end) offsets into the source text.
# ---------------------------------------------------------------------------

_TERM = set(" \t\r\n,{}[]()\";#^")


class EdnParseError(ValueError):
    """Any malformed EDN: unterminated string, unbalanced brackets, odd map."""


class EdnNode:
    __slots__ = ("start", "end")

    def __init__(self, start, end):
        self.start = start
        self.end = end


class EdnString(EdnNode):
    __slots__ = ("value",)

    def __init__(self, value, start, end):
        EdnNode.__init__(self, start, end)
        self.value = value


class EdnKeyword(EdnNode):
    __slots__ = ("name",)

    def __init__(self, name, start, end):
        EdnNode.__init__(self, start, end)
        self.name = name


class EdnSymbol(EdnNode):
    __slots__ = ("name",)

    def __init__(self, name, start, end):
        EdnNode.__init__(self, start, end)
        self.name = name


class EdnAtom(EdnNode):
    """Numbers, booleans, nil and character literals (kept as raw text)."""
    __slots__ = ("text",)

    def __init__(self, text, start, end):
        EdnNode.__init__(self, start, end)
        self.text = text


class EdnMap(EdnNode):
    __slots__ = ("entries",)

    def __init__(self, entries, start, end):
        EdnNode.__init__(self, start, end)
        self.entries = entries  # list of (key, value) nodes


class EdnVec(EdnNode):
    __slots__ = ("items",)

    def __init__(self, items, start, end):
        EdnNode.__init__(self, start, end)
        self.items = items


class EdnList(EdnNode):
    __slots__ = ("items",)

    def __init__(self, items, start, end):
        EdnNode.__init__(self, start, end)
        self.items = items


class EdnSet(EdnNode):
    __slots__ = ("items",)

    def __init__(self, items, start, end):
        EdnNode.__init__(self, start, end)
        self.items = items


class EdnTagged(EdnNode):
    __slots__ = ("tag", "form")

    def __init__(self, tag, form, start, end):
        EdnNode.__init__(self, start, end)
        self.tag = tag
        self.form = form


class EdnMeta(EdnNode):
    __slots__ = ("meta", "form")

    def __init__(self, meta, form, start, end):
        EdnNode.__init__(self, start, end)
        self.meta = meta
        self.form = form


_SKIPPED = object()  # marker for a `#_`-discarded form (yields no value)

_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
            "n": "\n", "r": "\r", "t": "\t"}


def _is_number(text):
    digits = "0123456789"
    s = text
    if s[:1] in ("+", "-") and len(s) > 1:
        s = s[1:]
    if not s or s[0] not in digits:
        return False
    i = 0
    while i < len(s) and s[i] in digits:
        i += 1
    if i == len(s):
        return True
    if s[i] == "." and i + 1 < len(s):
        j = i + 1
        while j < len(s) and s[j] in digits:
            j += 1
        if j == len(s):
            return True
    return False


class _Parser:
    def __init__(self, text):
        self.text = text
        self.n = len(text)
        self.pos = 0

    def fail(self, msg):
        line = self.text.count("\n", 0, self.pos) + 1
        raise EdnParseError("%s at line %d (offset %d)" % (msg, line, self.pos))

    def skip_trivia(self):
        while self.pos < self.n:
            c = self.text[self.pos]
            if c in " \t\r\n,":
                self.pos += 1
            elif c == ";":
                while self.pos < self.n and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def read_forms(self):
        forms = []
        while True:
            self.skip_trivia()
            if self.pos >= self.n:
                return forms
            if self.text[self.pos] in "}])":
                self.fail("unexpected %r" % self.text[self.pos])
            form = self.read_form()
            if form is not _SKIPPED:
                forms.append(form)

    def read_form(self):
        self.skip_trivia()
        if self.pos >= self.n:
            self.fail("unexpected end of input")
        c = self.text[self.pos]
        if c == "{":
            return self.read_map()
        if c == "[":
            return self.read_seq("[", "]", EdnVec)
        if c == "(":
            return self.read_seq("(", ")", EdnList)
        if c == '"':
            return self.read_string()
        if c == "#":
            return self.read_dispatch()
        if c == "^":
            return self.read_meta()
        if c == "\\":
            return self.read_char()
        if c in "}])":
            self.fail("unexpected %r" % c)
        return self.read_token()

    def read_map(self):
        start = self.pos
        self.pos += 1
        entries = []
        while True:
            self.skip_trivia()
            if self.pos >= self.n:
                self.fail("unclosed `{`")
            if self.text[self.pos] == "}":
                self.pos += 1
                return EdnMap(entries, start, self.pos)
            key = self.read_form()
            if key is _SKIPPED:
                continue
            while True:
                self.skip_trivia()
                if self.pos >= self.n:
                    self.fail("unclosed `{`")
                if self.text[self.pos] == "}":
                    self.fail("map literal must contain an even number of forms")
                val = self.read_form()
                if val is _SKIPPED:
                    continue
                entries.append((key, val))
                break

    def read_seq(self, opener, closer, cls):
        start = self.pos
        self.pos += 1
        items = []
        while True:
            self.skip_trivia()
            if self.pos >= self.n:
                self.fail("unclosed `%s`" % opener)
            if self.text[self.pos] == closer:
                self.pos += 1
                return cls(items, start, self.pos)
            form = self.read_form()
            if form is not _SKIPPED:
                items.append(form)

    def read_set(self):
        start = self.pos
        self.pos += 2  # consume `#{`
        items = []
        while True:
            self.skip_trivia()
            if self.pos >= self.n:
                self.fail("unclosed `#{`")
            if self.text[self.pos] == "}":
                self.pos += 1
                return EdnSet(items, start, self.pos)
            form = self.read_form()
            if form is not _SKIPPED:
                items.append(form)

    def read_dispatch(self):
        start = self.pos
        self.pos += 1
        if self.pos >= self.n:
            self.fail("orphan `#`")
        c = self.text[self.pos]
        if c == "_":
            self.pos += 1
            self.skip_trivia()
            if self.pos >= self.n or self.text[self.pos] in "}])":
                self.fail("orphan `#_`")
            self.read_form()  # exactly one form is discarded
            return _SKIPPED
        if c == "{":
            return self.read_set()
        j = self.pos
        while j < self.n and self.text[j] not in _TERM:
            j += 1
        tag = self.text[self.pos:j]
        if not tag:
            self.fail("orphan `#`")
        self.pos = j
        self.skip_trivia()
        if self.pos >= self.n or self.text[self.pos] in "}])":
            self.fail("orphan tag `#%s`" % tag)
        form = self.read_form()
        if form is _SKIPPED:
            self.fail("orphan tag `#%s`" % tag)
        return EdnTagged(tag, form, start, self.pos)

    def read_meta(self):
        start = self.pos
        self.pos += 1
        self.skip_trivia()
        if self.pos >= self.n or self.text[self.pos] in "}])":
            self.fail("orphan `^`")
        meta = self.read_form()
        if meta is _SKIPPED:
            self.fail("orphan `^`")
        self.skip_trivia()
        if self.pos >= self.n or self.text[self.pos] in "}])":
            self.fail("orphan `^`")
        form = self.read_form()
        if form is _SKIPPED:
            self.fail("orphan `^`")
        return EdnMeta(meta, form, start, self.pos)

    def read_char(self):
        start = self.pos
        self.pos += 1
        j = self.pos
        while j < self.n and self.text[j] not in _TERM:
            j += 1
        if j == self.pos:
            self.fail("orphan `\\`")
        self.pos = j
        return EdnAtom(self.text[start:j], start, self.pos)

    def read_string(self):
        start = self.pos
        self.pos += 1
        buf = []
        while True:
            if self.pos >= self.n:
                self.fail("unterminated string")
            c = self.text[self.pos]
            if c == '"':
                self.pos += 1
                return EdnString("".join(buf), start, self.pos)
            if c == "\\":
                if self.pos + 1 >= self.n:
                    self.fail("unterminated string")
                e = self.text[self.pos + 1]
                if e in _ESCAPES:
                    buf.append(_ESCAPES[e])
                    self.pos += 2
                elif e == "u":
                    h = self.text[self.pos + 2:self.pos + 6]
                    if len(h) != 4:
                        self.fail("bad unicode escape")
                    ok = True
                    for ch in h:
                        if ch not in "0123456789abcdefABCDEF":
                            ok = False
                    if not ok:
                        self.fail("bad unicode escape")
                    buf.append(chr(int(h, 16)))
                    self.pos += 6
                else:
                    self.fail("bad escape `\\%s`" % e)
            else:
                buf.append(c)
                self.pos += 1

    def read_token(self):
        start = self.pos
        while self.pos < self.n and self.text[self.pos] not in _TERM:
            self.pos += 1
        word = self.text[start:self.pos]
        if not word:
            self.fail("unexpected character")
        if word.startswith(":"):
            if len(word) == 1:
                self.fail("orphan `:`")
            return EdnKeyword(word, start, self.pos)
        if word in ("true", "false", "nil") or _is_number(word):
            return EdnAtom(word, start, self.pos)
        return EdnSymbol(word, start, self.pos)


def parse_edn(text):
    """Parse EDN text into top-level forms; `#_`-discarded forms are dropped."""
    return _Parser(text).read_forms()


# ---------------------------------------------------------------------------
# AST queries: the single source of truth for --check and rewrite.
# ---------------------------------------------------------------------------

_LIB_GROUPS = ("io.github.kotoba-lang/", "kotoba-lang/", "gftd/")
_ART_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                       "0123456789_.-")
_HEX = frozenset("0123456789abcdef")


def _is_lib_key(name):
    for group in _LIB_GROUPS:
        if name.startswith(group):
            art = name[len(group):]
            if not art:
                return False
            for c in art:
                if c not in _ART_CHARS:
                    return False
            return True
    return False


def walk_edn(node):
    yield node
    if isinstance(node, EdnMap):
        for key, val in node.entries:
            for sub in walk_edn(key):
                yield sub
            for sub in walk_edn(val):
                yield sub
    elif isinstance(node, (EdnVec, EdnList, EdnSet)):
        for item in node.items:
            for sub in walk_edn(item):
                yield sub
    elif isinstance(node, EdnTagged):
        for sub in walk_edn(node.form):
            yield sub
    elif isinstance(node, EdnMeta):
        for sub in walk_edn(node.meta):
            yield sub
        for sub in walk_edn(node.form):
            yield sub


def iter_lib_pins(forms):
    """(key_node, lib_name, coord_map) for each live `GROUP/artifact {...}` pin.

    Pins inside `;`-comments are trivia (never parsed); pins inside `#_`
    discards are dropped by the parser, so neither can be misdetected.
    """
    for form in forms:
        for node in walk_edn(form):
            if isinstance(node, EdnMap):
                for key, val in node.entries:
                    if (isinstance(key, EdnSymbol) and isinstance(val, EdnMap)
                            and _is_lib_key(key.name)):
                        yield key, key.name, val


def _map_str(coord, key_name):
    for key, val in coord.entries:
        if (isinstance(key, EdnKeyword) and key.name == key_name
                and isinstance(val, EdnString)):
            return val.value
    return None


def _map_has(coord, key_name):
    for key, _val in coord.entries:
        if isinstance(key, EdnKeyword) and key.name == key_name:
            return True
    return False


def _coord_sha(coord):
    return _map_str(coord, ":git/sha") or _map_str(coord, ":sha")


def _is_hex(text):
    if not text:
        return False
    for c in text:
        if c not in _HEX:
            return False
    return True


def _mono_url(url):
    return url == MONO_URL or url == MONO_URL + ".git"


def dead_url(coord):
    """github.com/kotoba-lang/<name> URL with <name> not in {kotoba(.git), amu(.git)}."""
    url = _map_str(coord, ":git/url")
    if url is None:
        return False
    prefix = "https://github.com/kotoba-lang/"
    if not url.startswith(prefix):
        return False
    rest = url[len(prefix):]
    if rest.endswith(".git"):
        rest = rest[:-len(".git")]
    if not rest or "/" in rest or rest in ("kotoba", "amu"):
        return False
    for c in rest:
        if c not in _ART_CHARS:
            return False
    return True


def bare_git_sha(coord):
    """:git/sha or :sha without any :git/url (default URL points at a deleted repo)."""
    if _map_has(coord, ":git/url"):
        return False
    return _is_hex(_map_str(coord, ":git/sha")) or _is_hex(_map_str(coord, ":sha"))


def has_local_root(coord):
    """:local/root present as a real key (never from a comment or discard)."""
    return _map_has(coord, ":local/root")


def is_canonical(coord, root, sha):
    url = _map_str(coord, ":git/url")
    if url is None or not _mono_url(url):
        return False
    return _coord_sha(coord) == sha and _map_str(coord, ":deps/root") == root


def _needs_rewrite(lib, coord, sha, rewrite_locals):
    if dead_url(coord) or bare_git_sha(coord):
        return True
    if has_local_root(coord) and lib.split("/", 1)[1] in rewrite_locals:
        return True
    url = _map_str(coord, ":git/url")
    if url is not None and _mono_url(url) and _coord_sha(coord) != sha:
        return True
    return False


def load_metadata(repo, sha):
    """Returns (alias_to_path, lib_deps, lib_text, resolve)."""
    cat = _read_tree_file(repo, sha, "lib/catalog.edn")
    if cat is None:
        sys.exit("error: cannot read lib/catalog.edn at %s from %s" % (sha, repo))
    try:
        cat_forms = parse_edn(cat)
    except EdnParseError as e:
        sys.exit("error: cannot parse lib/catalog.edn at %s from %s: %s"
                 % (sha, repo, e))
    alias_to_path = {}
    # Every group/artifact string inside an entry carrying a lib/ path maps
    # to that path (in practice these live in the :aliases vectors).
    for form in cat_forms:
        for node in walk_edn(form):
            if not isinstance(node, EdnMap):
                continue
            path = _map_str(node, ":path")
            if path is None or not path.startswith("lib/"):
                continue
            for sub in walk_edn(node):
                if isinstance(sub, EdnString) and _is_lib_key(sub.value):
                    alias_to_path[sub.value] = path

    lib_local_deps = {}  # path -> ([local lib names], [(lib, url, sha, root)] git edges)
    lib_texts = {}  # path -> raw deps.edn text (for pin inspection)
    lib_forms = {}  # path -> parsed AST (same text, no re-parse)

    def lib_deps(path):
        if path in lib_local_deps:
            return lib_local_deps[path]
        txt = _read_tree_file(repo, sha, path + "/deps.edn")
        if txt is None:
            lib_local_deps[path] = None
            return None
        lib_texts[path] = txt
        forms = parse_edn(txt)  # EdnParseError propagates to main (exit 3)
        lib_forms[path] = forms
        refs, gits = [], []
        for _key, lib, coord in iter_lib_pins(forms):
            if has_local_root(coord):
                refs.append(lib)
                continue
            url = _map_str(coord, ":git/url")
            gsha = _coord_sha(coord)
            if url is not None and gsha is not None and _is_hex(gsha):
                root = _map_str(coord, ":deps/root")
                gits.append((lib, url, gsha, root if root is not None else ""))
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
        for path, forms in lib_forms.items():
            for _key, name, coord in iter_lib_pins(forms):
                if name != lib:
                    continue
                root = _map_str(coord, ":local/root")
                if root is not None and root.startswith("../"):
                    rest = root[len("../"):]
                    if not rest or "/" in rest:
                        continue
                    ok = True
                    for c in rest:
                        if c not in _ART_CHARS:
                            ok = False
                    if ok:
                        cands.append("lib/" + rest)
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


def rewrite_direct(text, resolve, sha, rewrite_locals):
    """Pass 1: rewrite dead pins. Returns (text, [rewritten artifacts]).

    Only io.github.kotoba-lang|kotoba-lang|gftd groups are scanned.
    cognitect test-runner's bare :git/tag+:git/sha uses another group
    and never reaches here, so every bare sha here defaults to a deleted
    kotoba-lang repo. One pin per iteration (re-parsed each time, so spans
    stay exact); `#_`-discarded pins are invisible to the parser.
    """
    changed = []
    guard = 0
    while guard < 1000:
        guard += 1
        forms = parse_edn(text)
        target = None
        for key, lib, coord in iter_lib_pins(forms):
            if lib in AMU_LIBS:
                continue  # amu is frozen
            if not _needs_rewrite(lib, coord, sha, rewrite_locals):
                continue
            root = resolve(lib)
            if is_canonical(coord, root, sha):
                continue
            target = (key, lib, coord, root)
            break
        if target is None:
            return text, changed
        key, lib, coord, root = target
        new = (text[key.start:key.end] + "\n        {:git/url \"%s\"\n"
               "         :git/sha \"%s\"\n"
               "         :deps/root \"%s\"}") % (MONO_URL, sha, root)
        text = text[:key.start] + new + text[coord.end:]
        changed.append(lib.split("/", 1)[1])
    raise EdnParseError("rewrite did not converge")


def current_tops(text, sha):
    """Artifacts holding monorepo-URL pins at sha (the live basis tops)."""
    tops = set()
    for _key, lib, coord in iter_lib_pins(parse_edn(text)):
        if lib in AMU_LIBS:
            continue
        url = _map_str(coord, ":git/url")
        if url is not None and _mono_url(url) and _coord_sha(coord) == sha:
            tops.add(lib.split("/", 1)[1])
    return tops


def present_groups(text):
    """artifact -> {full lib keys used in the file} for kotoba-lang/gftd groups."""
    out = {}
    for _key, lib, _coord in iter_lib_pins(parse_edn(text)):
        if lib in AMU_LIBS:
            continue
        out.setdefault(lib.split("/", 1)[1], set()).add(lib)
    return out


def gftd_arts(text):
    """Artifacts referenced as live gftd/<art> pins (never from comments/discards)."""
    arts = set()
    for _key, lib, _coord in iter_lib_pins(parse_edn(text)):
        if lib.startswith("gftd/"):
            arts.add(lib.split("/", 1)[1])
    return arts


def _aliases_map(forms):
    for form in forms:
        for node in walk_edn(form):
            if isinstance(node, EdnMap):
                for key, val in node.entries:
                    if (isinstance(key, EdnKeyword) and key.name == ":aliases"
                            and isinstance(val, EdnMap)):
                        return val
    return None


def _has_replace_deps(body):
    for key, val in body.entries:
        if (isinstance(key, EdnKeyword) and key.name == ":replace-deps"
                and isinstance(val, EdnMap)):
            return True
    return False


def _alias_has_amu(body):
    for node in walk_edn(body):
        if isinstance(node, EdnMap):
            for key, val in node.entries:
                if (isinstance(key, EdnSymbol) and isinstance(val, EdnMap)
                        and key.name in ("io.github.kotoba-lang/amu", "kotoba-lang/amu")
                        and (_map_has(val, ":git/url") or _map_has(val, ":git/sha"))):
                    return True
    return False


def entry_text(lib, root, sha, indent):
    return ("%s%s\n"
            "%s{:git/url \"%s\"\n"
            "%s :git/sha \"%s\"\n"
            "%s :deps/root \"%s\"}") % (
        indent, lib, indent, MONO_URL, indent, sha, indent, root)


def last_entry_indent(map_text):
    lines = map_text.split("\n")
    for ln in reversed(lines):
        stripped = ln.lstrip(" \t")
        if stripped.startswith(_LIB_GROUPS):
            rest = stripped.split("/", 1)[1]
            if rest and rest[0] in _ART_CHARS:
                return ln[:len(ln) - len(stripped)]
    middle = lines[1:-1] if len(lines) > 2 else lines
    for ln in reversed(middle):
        stripped = ln.lstrip(" \t")
        if stripped:
            return ln[:len(ln) - len(stripped)]
    return " " * 39


_KEY_INDENT_KEYS = (":extra-deps", ":replace-deps", ":main-opts",
                    ":exec-fn", ":extra-paths", ":jvm-opts")
_WORD_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                        "0123456789_")


def _body_key_indent(inner):
    found = None
    for line in inner.split("\n"):
        i = 0
        while i < len(line) and line[i] == " ":
            i += 1
        if i == 0:
            continue
        rest = line[i:]
        for key in _KEY_INDENT_KEYS:
            if rest.startswith(key):
                nxt = rest[len(key):len(key) + 1]
                if nxt == "" or nxt not in _WORD_CHARS:
                    found = line[:i]
    return found if found is not None else " " * 14


def ensure_override_in_alias(text, body, sha, want, resolve):
    """Merge :override-deps pins for want into this alias body.

    One edit per call (the caller re-parses); spans are absolute offsets.
    """
    if not want:
        return text, False
    override = None
    for key, val in body.entries:
        if (isinstance(key, EdnKeyword) and key.name == ":override-deps"
                and isinstance(val, EdnMap)):
            override = val
            break
    if override is not None:
        o_open, o_close = override.start, override.end
        for lib in sorted(want):
            root = resolve(lib)
            found = None
            for key, val in override.entries:
                if (isinstance(key, EdnSymbol) and key.name == lib
                        and isinstance(val, EdnMap)):
                    found = (key, val)
                    break
            ins = last_entry_indent(text[o_open:o_close])
            if found is not None:
                key, val = found
                if is_canonical(val, root, sha):
                    continue
                new_text = (text[:key.start] + entry_text(lib, root, sha, ins)
                            + text[val.end:])
                return new_text, True
            entry = "\n" + entry_text(lib, root, sha, ins)
            inner = text[o_open:o_close - 1].rstrip("\n")
            return text[:o_open] + inner + entry + "}" + text[o_close:], True
        return text, False
    inner = text[body.start:body.end]
    key_indent = _body_key_indent(inner)
    mi = key_indent + " " * len(":override-deps {")
    roots = {}
    for lib in want:
        roots[lib.split("/", 1)[1]] = resolve(lib)
    lines = [entry_text(lib, roots[lib.split("/", 1)[1]], sha, mi)
             for lib in sorted(want)]
    block = "\n%s:override-deps {%s\n%s}" % (
        key_indent, "".join("\n" + e for e in lines), key_indent)
    head = text[:body.end - 1].rstrip("\n")
    return head + block + "}" + text[body.end:], True


def rewrite_aliases(text, tops, resolve, lib_deps, dual_arts, sha):
    present = present_groups(text)
    changed = []
    guard = 0
    while guard < 60:
        guard += 1
        aliases = _aliases_map(parse_edn(text))
        if aliases is None:
            return text, changed
        progressed = False
        for key, body in [(k, v) for k, v in aliases.entries
                          if isinstance(k, EdnKeyword) and isinstance(v, EdnMap)]:
            name = key.name
            if name == ":test" and _has_replace_deps(body):
                continue
            amu = _alias_has_amu(body)
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
            new_text, did = ensure_override_in_alias(text, body, sha, subwant,
                                                     resolve)
            if did:
                text = new_text
                present = present_groups(text)
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
    try:
        forms = parse_edn(text)
    except EdnParseError as e:
        print("check failed (%s):" % path)
        print("  unbalanced EDN: %s" % e)
        return 1
    problems = []
    for key, lib, coord in iter_lib_pins(forms):
        if lib in AMU_LIBS:
            continue
        # Actual map keys and string values only: a :git/url living inside
        # a `;`-comment or a `#_` discard is trivia, never a coordinate.
        url = _map_str(coord, ":git/url")
        if url is not None and dead_url(coord):
            lineno = text.count("\n", 0, key.start) + 1
            problems.append("%d: dead repo URL %s" % (lineno, url))
        elif bare_git_sha(coord):
            lineno = text.count("\n", 0, key.start) + 1
            problems.append("%d: bare git sha without :git/url: %s" % (lineno, lib))
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
        new_text, direct = rewrite_direct(text, resolve, args.sha,
                                          set(a for a in args.rewrite_local_roots.split(",")
                                              if a))
        # tops after pass 1: freshly rewritten pins count too
        tops = current_tops(new_text, args.sha)
        # Live gftd/ pins only: a gftd/... mention inside a `;`-comment,
        # a "..." string or a `#_` discard is not a pin the rewrite pass sees.
        dual_arts = gftd_arts(new_text)
        new_text, aliases = rewrite_aliases(new_text, tops, resolve,
                                            lib_deps, dual_arts, args.sha)
    except EdnParseError as e:
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
