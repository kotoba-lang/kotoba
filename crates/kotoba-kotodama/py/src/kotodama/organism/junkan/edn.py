"""junkan.edn — EDN wire-format serialization for the datom layer.

ADR-2605262130 + ADR-2605312345 (kotoba Datom = first-class canonical
state). The ``DatomStore`` reference model holds immutable ``[E A V T]``
facts; **kotoba-kqe** is the canonical production binding. The wire format
both speak is **EDN** (Extensible Data Notation — Clojure/Datomic's
serialization), so a passive sensor observation can be transacted into
kotoba as Datomic-isomorphic tx-data.

This module supplies the missing bridge:

  sensor Observation  ──datoms_from_dataclass──▶  [(e, a, v), ...]
  (e, a, v) facts     ──datoms_to_tx_edn──────▶  "[[:db/add e a v] ...]"   (kotoba ingest)
  Datom [E A V T]     ──datom_to_eavt_edn─────▶  "[e a v t]"               (raw immutable fact)
  DatomStore          ──store_to_tx_edn───────▶  full EDN tx-data dump

Pure + offline (no network, no inference) — consistent with the junkan
analysis-only discipline (G4). Proprietary Datomic is NOT used; this emits
the open EDN text that kotoba-kqe ingests (Charter Rider §2(e)+§2(c)).
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from typing import Any, Iterable

__all__ = [
    "Keyword",
    "kw",
    "to_edn",
    "datom_to_eavt_edn",
    "datoms_to_tx_edn",
    "entity_to_edn",
    "store_to_tx_edn",
    "datoms_from_dataclass",
    "ns_for",
    "EdnError",
    "read_edn",
    "read_all_edn",
    "parse_tx_edn",
]


class EdnError(ValueError):
    """Raised on malformed EDN input during reading."""


class Keyword(str):
    """An EDN keyword (``:foo`` / ``:ns/attr``). Serialized WITHOUT quotes.

    A plain ``str`` value serializes as a quoted EDN string; wrap it in
    ``Keyword`` (or use :func:`kw`) to emit it as a keyword instead.
    """

    __slots__ = ()


def kw(s: str) -> Keyword:
    """Coerce ``s`` to an EDN :class:`Keyword`, adding a leading ``:``."""
    return Keyword(s if s.startswith(":") else f":{s}")


_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
}


def _escape(s: str) -> str:
    return "".join(_ESCAPES.get(c, c) for c in s)


def to_edn(value: Any) -> str:
    """Serialize a Python value to an EDN string (Datomic/kotoba wire form).

    Mapping: ``None``→``nil`` · ``bool``→``true``/``false`` ·
    :class:`Keyword`→bare keyword · ``str``→quoted+escaped ·
    ``int``/``float`` → numeric literal · ``dict``→EDN map ·
    ``set``/``frozenset``→EDN set ``#{...}`` · ``list``/``tuple``→EDN vector
    ``[...]`` · ``datetime``→``#inst "…"``.
    """
    # NB: bool BEFORE int (bool is an int subclass); Keyword BEFORE str.
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Keyword):
        return str(value)
    if isinstance(value, str):
        return f'"{_escape(value)}"'
    if isinstance(value, (_dt.datetime, _dt.date)):
        return f'#inst "{value.isoformat()}"'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        inner = " ".join(f"{to_edn(k)} {to_edn(v)}" for k, v in value.items())
        return "{" + inner + "}"
    if isinstance(value, (set, frozenset)):
        inner = " ".join(to_edn(v) for v in value)
        return "#{" + inner + "}"
    if isinstance(value, (list, tuple)):
        inner = " ".join(to_edn(v) for v in value)
        return "[" + inner + "]"
    raise TypeError(f"to_edn: unsupported type {type(value).__name__}")


def datom_to_eavt_edn(datom: Any) -> str:
    """Serialize a :class:`~.datom.Datom` as a raw EAVT tuple ``[e a v t]``.

    ``e`` is emitted as an EDN string (entity id), ``a`` as a keyword.
    """
    return (
        "["
        + to_edn(datom.e)
        + " "
        + to_edn(kw(datom.a))
        + " "
        + to_edn(datom.v)
        + " "
        + to_edn(datom.t)
        + "]"
    )


def datoms_to_tx_edn(facts: Iterable[tuple[str, str, Any]]) -> str:
    """Serialize ``(e, a, v)`` facts as Datomic tx-data ``[[:db/add e a v] …]``.

    This is the form kotoba-kqe ingests: a vector of ``:db/add`` assertions.
    """
    assertions = [
        "[" + to_edn(kw(":db/add")) + " " + to_edn(e) + " " + to_edn(kw(a)) + " " + to_edn(v) + "]"
        for (e, a, v) in facts
    ]
    return "[" + " ".join(assertions) + "]"


def entity_to_edn(entity_id: str, attrs: dict[str, Any]) -> str:
    """Serialize one entity as an EDN map ``{:db/id eid :a v …}``.

    ``attrs`` keys are namespaced attribute strings (``"legal.statute/citation"``
    or ``":legal.statute/citation"``); they become EDN keywords.
    """
    pairs = [to_edn(kw(":db/id")) + " " + to_edn(entity_id)]
    for a, v in attrs.items():
        pairs.append(to_edn(kw(a)) + " " + to_edn(v))
    return "{" + " ".join(pairs) + "}"


def store_to_tx_edn(store: Any) -> str:
    """Serialize every fact in a ``DatomStore`` as one EDN tx-data vector.

    Preserves the append-only order (and thus tx ``t`` ordering). Useful for
    a full-store dump / hand-off into kotoba-kqe.
    """
    return datoms_to_tx_edn((d.e, d.a, d.v) for d in store._datoms)  # noqa: SLF001


# ── Observation → datoms bridge ───────────────────────────────────────────


def _kebab(name: str) -> str:
    return name.replace("_", "-")


def ns_for(obj: Any) -> str:
    """Derive a datom attribute namespace from a dataclass type name.

    ``LegalStatuteObservation`` → ``"legal.statute"`` ·
    ``SensorObservation`` → ``"sensor"`` ·
    ``CorpRegistryObservation`` → ``"corp.registry"``.
    """
    cls_name = type(obj).__name__
    if cls_name.endswith("Observation"):
        cls_name = cls_name[: -len("Observation")]
    parts: list[str] = []
    cur = ""
    for ch in cls_name:
        if ch.isupper() and cur:
            parts.append(cur)
            cur = ch.lower()
        else:
            cur += ch.lower()
    if cur:
        parts.append(cur)
    return ".".join(parts) or "fact"


def datoms_from_dataclass(
    obj: Any,
    *,
    entity_id: str,
    ns: str | None = None,
    skip: Iterable[str] = (),
    skip_none: bool = True,
) -> list[tuple[str, str, Any]]:
    """Map a (frozen) dataclass instance to ``(entity_id, attr, value)`` facts.

    Each field ``f`` becomes attribute ``:<ns>/<kebab-f>``. ``ns`` defaults to
    :func:`ns_for`. ``None`` values are dropped by default (Datomic stores no
    nil). Fields named in ``skip`` are omitted. Tuples/lists pass through as
    EDN vectors at serialization time.

    Raises ``TypeError`` if ``obj`` is not a dataclass instance.
    """
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        raise TypeError("datoms_from_dataclass expects a dataclass instance")
    namespace = ns if ns is not None else ns_for(obj)
    skip_set = set(skip)
    out: list[tuple[str, str, Any]] = []
    for f in dataclasses.fields(obj):
        if f.name in skip_set:
            continue
        v = getattr(obj, f.name)
        if skip_none and v is None:
            continue
        out.append((entity_id, f":{namespace}/{_kebab(f.name)}", v))
    return out


# ── EDN reader (round-trip of the subset to_edn emits) ────────────────────


_TERMINATORS = set(' \t\r\n,[]{}()"')


class _EdnReader:
    """Recursive-descent reader for the EDN subset :func:`to_edn` emits.

    Supports: nil / true / false, keywords (``:ns/attr``), strings (with
    ``\\\\ \\" \\n \\t \\r`` escapes), ints, floats, vectors ``[…]``, maps
    ``{…}``, sets ``#{…}`` and the ``#inst "…"`` tagged literal. Commas are
    whitespace (EDN semantics). Bare symbols are not emitted by ``to_edn``
    and are rejected.
    """

    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0
        self.n = len(text)

    def _skip_ws(self) -> None:
        while self.i < self.n and (self.s[self.i].isspace() or self.s[self.i] == ","):
            self.i += 1

    def at_end(self) -> bool:
        self._skip_ws()
        return self.i >= self.n

    def read(self) -> Any:
        self._skip_ws()
        if self.i >= self.n:
            raise EdnError("unexpected end of input")
        c = self.s[self.i]
        if c == '"':
            return self._read_string()
        if c == ":":
            return self._read_keyword()
        if c == "[":
            return self._read_seq("]")
        if c == "{":
            return self._read_map()
        if c == "#":
            return self._read_dispatch()
        return self._read_atom()

    def _read_string(self) -> str:
        self.i += 1  # opening quote
        out: list[str] = []
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":
                self.i += 1
                if self.i >= self.n:
                    raise EdnError("unterminated escape in string")
                esc = self.s[self.i]
                out.append(
                    {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(esc, esc)
                )
                self.i += 1
                continue
            if c == '"':
                self.i += 1
                return "".join(out)
            out.append(c)
            self.i += 1
        raise EdnError("unterminated string")

    def _read_token(self) -> str:
        start = self.i
        while self.i < self.n and self.s[self.i] not in _TERMINATORS:
            self.i += 1
        return self.s[start:self.i]

    def _read_keyword(self) -> "Keyword":
        tok = self._read_token()  # includes leading ':'
        return Keyword(tok)

    def _read_seq(self, close: str) -> list:
        self.i += 1  # opening bracket
        out: list[Any] = []
        while True:
            self._skip_ws()
            if self.i >= self.n:
                raise EdnError(f"unterminated sequence, expected '{close}'")
            if self.s[self.i] == close:
                self.i += 1
                return out
            out.append(self.read())

    def _read_map(self) -> dict:
        self.i += 1  # '{'
        out: dict[Any, Any] = {}
        while True:
            self._skip_ws()
            if self.i >= self.n:
                raise EdnError("unterminated map, expected '}'")
            if self.s[self.i] == "}":
                self.i += 1
                return out
            k = self.read()
            v = self.read()
            out[k] = v

    def _read_dispatch(self) -> Any:
        self.i += 1  # '#'
        if self.i < self.n and self.s[self.i] == "{":
            return set(self._read_seq("}"))
        tag = self._read_token()
        if tag == "inst":
            self._skip_ws()
            iso = self._read_string()
            try:
                return _dt.datetime.fromisoformat(iso)
            except ValueError as exc:  # pragma: no cover - defensive
                raise EdnError(f"bad #inst literal: {iso!r}") from exc
        raise EdnError(f"unsupported dispatch tag #{tag}")

    def _read_atom(self) -> Any:
        tok = self._read_token()
        if not tok:
            raise EdnError(f"unexpected character {self.s[self.i]!r}")
        if tok == "nil":
            return None
        if tok == "true":
            return True
        if tok == "false":
            return False
        try:
            return int(tok)
        except ValueError:
            pass
        try:
            return float(tok)
        except ValueError:
            pass
        raise EdnError(f"unsupported bare symbol {tok!r} (to_edn emits no symbols)")


def read_edn(text: str) -> Any:
    """Parse a single EDN form. Raises :class:`EdnError` on malformed input.

    Round-trips the subset :func:`to_edn` emits. Note: EDN vectors read back
    as ``list`` (so a tuple serialized via :func:`to_edn` returns as a list),
    and keywords read back as :class:`Keyword`.
    """
    r = _EdnReader(text)
    val = r.read()
    if not r.at_end():
        raise EdnError("trailing data after EDN form")
    return val


def read_all_edn(text: str) -> list[Any]:
    """Parse zero or more whitespace-separated top-level EDN forms."""
    r = _EdnReader(text)
    out: list[Any] = []
    while not r.at_end():
        out.append(r.read())
    return out


def parse_tx_edn(text: str) -> list[tuple[str, "Keyword", Any]]:
    """Parse Datomic tx-data ``[[:db/add e a v] …]`` back to ``(e, a, v)`` facts.

    Inverse of :func:`datoms_to_tx_edn`. Validates each assertion is a
    4-vector led by the ``:db/add`` keyword. Raises :class:`EdnError`
    otherwise (``:db/retract`` is rejected — G9 append-only).
    """
    forms = read_edn(text)
    if not isinstance(forms, list):
        raise EdnError("tx-data must be a vector of assertions")
    facts: list[tuple[str, Keyword, Any]] = []
    for a in forms:
        if not isinstance(a, list) or len(a) != 4:
            raise EdnError(f"assertion must be a 4-vector, got {a!r}")
        op, e, attr, v = a
        if op != ":db/add":
            raise EdnError(f"only :db/add is accepted (G9 append-only), got {op!r}")
        facts.append((e, attr, v))
    return facts
