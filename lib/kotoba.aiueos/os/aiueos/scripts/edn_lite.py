#!/usr/bin/env python3
"""edn_lite.py -- the minimum EDN reader/writer the Node-free image-route
tools need (os/aiueos/scripts/k16-pure-native-gate.py, image-freshness.py).

WHY THIS EXISTS. The K16 gate and the image-freshness receipt were nbb
scripts, and nbb is a Node host: `command -v nbb` gating the build put
NBB/Node inside the accepted build path, which the JUN-31 acceptance
criteria forbid (no C, NBB/Node, JVM or GraalVM path in the accepted build;
Python is orchestration only). The two tools are pure byte/EDN/git
orchestration, so they moved to Python. Both read and write EDN receipts, so
they need an EDN codec -- and this repository carries no Python EDN library.

WHAT IT SUPPORTS, measured against the EDN this repository actually writes
(os/aiueos/kotoba/provenance.edn, 116 receipts): nil, booleans, integers,
floats, strings (with \\", \\\\, \\n, \\t, \\r, \\b, \\f, \\uXXXX escapes),
keywords, symbols, lists, vectors, maps, sets, ;-comments, whitespace and
commas. Everything else -- reader tags (#inst), regex literals, character
literals -- raises EdnError rather than guessing: a receipt that this reader
mis-parses is exactly the silent-corruption failure the gate exists to stop.

VALUE MODEL: map -> dict, vector/list -> list, set -> frozenset, keyword ->
Kw, symbol -> Sym, string -> str, integer -> int, float -> float, nil ->
None, boolean -> bool. vector and list are deliberately NOT distinguished:
the parity harness compares receipt VALUES across two implementations, and
the callers only ever write vectors.

The writer (pr_str) is deterministic: dict keys are emitted in insertion
order. The nbb scripts write maps through cljs pr-str, whose hash-map
iteration order is not insertion order, so receipt TEXT is not byte-identical
between the two implementations -- equality is by EDN value, which is what
every reader (clojure.edn included) sees.
"""

from __future__ import annotations

import re


class EdnError(ValueError):
    """An EDN form this reader refuses to guess at."""


class Kw:
    """An EDN keyword. Identity is its printed name, ':foo/bar'."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name  # without the leading ':'

    def __str__(self) -> str:
        return ":" + self.name

    def __repr__(self) -> str:
        return ":" + self.name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Kw) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("edn-kw", self.name))


class Sym(str):
    """An EDN symbol (a str subclass; printed bare)."""


_DELIMS = set("()[]{}\"';,")
_WS = set(" \t\n\r\f,")


class _Reader:
    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0

    def eof(self) -> bool:
        return self.i >= len(self.s)

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def skip_ws(self) -> None:
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in _WS:
                self.i += 1
            elif c == ";":
                while self.i < len(self.s) and self.s[self.i] != "\n":
                    self.i += 1
            else:
                return

    def read(self):
        self.skip_ws()
        if self.eof():
            raise EdnError("unexpected end of input")
        c = self.s[self.i]
        if c == "(":
            return self._read_seq("(", ")")
        if c == "[":
            return self._read_seq("[", "]")
        if c == "{":
            return self._read_map()
        if c == '"':
            return self._read_string()
        if c == ":":
            return self._read_keyword()
        if c == "\\":
            raise EdnError("character literals are not supported")
        if c == "#":
            return self._read_dispatch()
        return self._read_token()

    def _read_seq(self, open_c: str, close_c: str) -> list:
        assert self.s[self.i] == open_c
        self.i += 1
        out = []
        while True:
            self.skip_ws()
            if self.eof():
                raise EdnError(f"unterminated {open_c}")
            if self.s[self.i] == close_c:
                self.i += 1
                return out
            out.append(self.read())

    def _read_map(self) -> dict:
        assert self.s[self.i] == "{"
        self.i += 1
        out = {}
        while True:
            self.skip_ws()
            if self.eof():
                raise EdnError("unterminated {")
            if self.s[self.i] == "}":
                self.i += 1
                return out
            key = self.read()
            self.skip_ws()
            if self.eof() or self.s[self.i] == "}":
                raise EdnError("map with a key and no value")
            out[key] = self.read()

    def _read_string(self) -> str:
        assert self.s[self.i] == '"'
        self.i += 1
        buf = []
        while True:
            if self.i >= len(self.s):
                raise EdnError("unterminated string")
            c = self.s[self.i]
            self.i += 1
            if c == '"':
                return "".join(buf)
            if c == "\\":
                if self.i >= len(self.s):
                    raise EdnError("unterminated escape")
                e = self.s[self.i]
                self.i += 1
                if e == "n":
                    buf.append("\n")
                elif e == "t":
                    buf.append("\t")
                elif e == "r":
                    buf.append("\r")
                elif e == "b":
                    buf.append("\b")
                elif e == "f":
                    buf.append("\f")
                elif e == '"':
                    buf.append('"')
                elif e == "\\":
                    buf.append("\\")
                elif e == "u":
                    hex4 = self.s[self.i : self.i + 4]
                    if len(hex4) < 4 or not re.fullmatch(r"[0-9a-fA-F]{4}", hex4):
                        raise EdnError("bad \\u escape")
                    self.i += 4
                    buf.append(chr(int(hex4, 16)))
                else:
                    raise EdnError(f"unsupported string escape \\{e}")
            else:
                buf.append(c)

    def _read_keyword(self) -> Kw:
        start = self.i
        self.i += 1  # ':'
        if self.peek() == ":":
            raise EdnError("auto-resolved keywords (::x) are not supported")
        name = self._token_text()
        if not name:
            raise EdnError("empty keyword")
        return Kw(name)

    def _token_text(self) -> str:
        start = self.i
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in _DELIMS or c in _WS:
                break
            self.i += 1
        return self.s[start : self.i]

    def _read_token(self):
        tok = self._token_text()
        if not tok:
            raise EdnError(f"empty token at offset {self.i}")
        if tok == "nil":
            return None
        if tok == "true":
            return True
        if tok == "false":
            return False
        if re.fullmatch(r"[-+]?\d+N?", tok):
            return int(tok.rstrip("N"))
        if re.fullmatch(r"[-+]?\d+\.\d+([eE][-+]?\d+)?M?", tok):
            return float(tok.rstrip("M"))
        if re.fullmatch(r"[-+]?\d+[eE][-+]?\d+M?", tok):
            return float(tok.rstrip("M"))
        if re.fullmatch(r"[+\-]", tok):
            return Sym(tok)
        if re.fullmatch(r"[A-Za-z*+!_?<>=./'&#-][A-Za-z0-9*+!_?<>=./'&#-]*", tok):
            return Sym(tok)
        raise EdnError(f"unsupported token {tok!r}")

    def _read_dispatch(self):
        c = self.peek()
        if c == "{":
            self.i += 1
            out = set()
            while True:
                self.skip_ws()
                if self.eof():
                    raise EdnError("unterminated #{")
                if self.s[self.i] == "}":
                    self.i += 1
                    return frozenset(out)
                out.add(self.read())
        if c == "_":
            self.i += 1
            self.read()  # discarded
            return self.read()
        raise EdnError("reader tags and regex literals are not supported")


def read_edn(text: str):
    r = _Reader(text)
    value = r.read()
    r.skip_ws()
    if not r.eof():
        raise EdnError(f"trailing content at offset {r.i}")
    return value


_STR_ESCAPE = {
    '"': '\\"',
    "\\": "\\\\",
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
    "\b": "\\b",
    "\f": "\\f",
}


def _pr(value) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (Kw, Sym)):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        out = ['"']
        for ch in value:
            if ch in _STR_ESCAPE:
                out.append(_STR_ESCAPE[ch])
            elif ord(ch) < 0x20:
                out.append(f"\\u{ord(ch):04x}")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_pr(k)} {_pr(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (set, frozenset)):
        return "#{" + " ".join(_pr(v) for v in value) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + " ".join(_pr(v) for v in value) + "]"
    raise EdnError(f"cannot print {type(value).__name__}")


def pr_str(value) -> str:
    return _pr(value)
