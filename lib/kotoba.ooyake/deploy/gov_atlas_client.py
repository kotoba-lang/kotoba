#!/usr/bin/env python3
"""ooyake 公 — shared gov-atlas READ client (ADR-2606021600).

The one read API every consumer of the read-side SSoT uses — danjo (audit),
kanae (fiscal viz), tsumugi (power-graph), toritsugi (citizen concierge), himotoki
(disclosure). Implements the query surface the lexicons declare
(getUnit / resolvePath / findService / searchUnits) over the committed registry
(auto-globbed: registry/gov-units*.edn — the FULL ~7,100-unit atlas). READ-ONLY (G9): pure functions,
no government interaction, no mutation, offline, no fabrication.

In production these same calls run against the kotoba gov-atlas-v1 graph (and the
public /.well-known/gov-units.json index); this module is the canonical, testable
reference implementation that loads the committed EDN registry directly.

API:
    a = GovAtlas()
    a.get_unit("gov.jpn.mof")                 -> unit dict | None
    a.resolve_path("gov.jpn.mof.nta")         -> [root..leaf] units
    a.children("gov.jpn")                      -> [unit, …]
    a.by_level("prefecture") / a.by_jurisdiction("jpn")
    a.search("財務")                           -> [unit, …]
    a.by_branch("judicial") / a.addresses_for(uid) / a.country_profile("fra")
    a.resolve_procedure("jp-juminhyo-utsushi") -> {owner, windows, addresses, forms, …}
    a.find_service("住民票")                   -> [resolution, …]   (findService)
"""
from __future__ import annotations

import glob
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))


# ── minimal EDN reader ────────────────────────────────────────────────────────
def parse_edn(src):
    i, n = 0, len(src)

    def skip():
        nonlocal i
        while i < n:
            c = src[i]
            if c in " \t\r\n,":
                i += 1; continue
            if c == ";":
                while i < n and src[i] != "\n":
                    i += 1
                continue
            break

    def read():
        nonlocal i
        skip(); c = src[i]
        return rs() if c == '"' else rm() if c == "{" else rv() if c == "[" else ra()

    def rs():
        nonlocal i
        i += 1; o = []
        while i < n:
            c = src[i]; i += 1
            if c == "\\":
                e = src[i]; i += 1; o.append({"n": "\n", "t": "\t", "r": "\r"}.get(e, e))
            elif c == '"':
                return "".join(o)
            else:
                o.append(c)
        raise ValueError("str")

    def rv():
        nonlocal i
        i += 1; a = []
        while True:
            skip()
            if src[i] == "]":
                i += 1; return a
            a.append(read())

    def rm():
        nonlocal i
        i += 1; d = {}
        while True:
            skip()
            if src[i] == "}":
                i += 1; return d
            k = read(); d[k] = read()

    def ra():
        nonlocal i
        s = i
        while i < n and src[i] not in " \t\r\n,;{}[]\"":
            i += 1
        t = src[s:i]
        if t in ("true", "false", "nil"):
            return {"true": True, "false": False, "nil": None}[t]
        if t.startswith(":"):
            return t
        try:
            return int(t)
        except ValueError:
            try:
                return float(t)
            except ValueError:
                return t

    skip(); return read()


def _kw(v):
    return v[1:] if isinstance(v, str) and v.startswith(":") else v


class GovAtlas:
    def __init__(self, registry_dir: str = _REG):
        self.units, self.addrs, self.windows, self.forms, self.procs = {}, {}, {}, {}, {}
        # Load the FULL committed atlas — every gov-units*.edn (countries, ministries,
        # legislatures, courts, central banks, oversight/regulatory bodies, ADM1
        # subdivisions, IGOs, …), not just the *.seed.edn core. (Pre-2026-06-04 this
        # globbed only `*.seed.edn`, so consumers saw ~28 of the ~7,100 units.)
        for f in sorted(glob.glob(os.path.join(registry_dir, "gov-units*.edn"))):
            doc = parse_edn(open(f, encoding="utf-8").read())
            for u in doc.get(":units", []):
                self.units[u[":gov.unit/id"]] = u
            for a in doc.get(":addresses", []):
                self.addrs[a[":gov.address/id"]] = a
            for w in doc.get(":windows", []):
                self.windows[w[":gov.window/id"]] = w
            for fm in doc.get(":forms", []):
                self.forms[fm[":gov.form/id"]] = fm
            for p in doc.get(":procedures", []):
                self.procs[p[":gov.procedure/id"]] = p

    # ── getUnit / resolvePath / children / facets ────────────────────────────
    def get_unit(self, uid):
        return self.units.get(uid)

    def resolve_path(self, uid):
        chain, cur, seen = [], self.units.get(uid), set()
        while cur and cur[":gov.unit/id"] not in seen:
            seen.add(cur[":gov.unit/id"])
            chain.append(cur)
            cur = self.units.get(cur.get(":gov.unit/parent"))
        return list(reversed(chain))

    def children(self, uid):
        return [u for u in self.units.values() if u.get(":gov.unit/parent") == uid]

    def by_level(self, level):
        return [u for u in self.units.values() if _kw(u.get(":gov.unit/level")) == level]

    def by_jurisdiction(self, cc):
        return [u for u in self.units.values()
                if (u.get(":gov.unit/jurisdiction") or "").split("-")[0] == cc]

    def search(self, q):
        q = q.lower()
        return [u for u in self.units.values()
                if q in (u.get(":gov.unit/name-local") or "").lower()
                or q in (u.get(":gov.unit/name-en") or "").lower()
                or q in u[":gov.unit/id"].lower()]

    def by_branch(self, branch):
        """All units of a branch of state (:executive/:legislative/:judicial/
        :independent/:local/:intergovernmental)."""
        return [u for u in self.units.values() if _kw(u.get(":gov.unit/branch")) == branch]

    def addresses_for(self, uid):
        """All :gov.address records keyed to a unit (HQ / seat / capital / 窓口)."""
        return [a for a in self.addrs.values() if a.get(":gov.address/unit") == uid]

    def country_profile(self, cc):
        """A country's full structural profile: the country unit, its national bodies
        grouped by branch, a subdivision count, and how many bodies carry a coordinate.
        The one-call view consumers (danjo/kanae/tsumugi/toritsugi) want."""
        cc = cc.lower()
        country = self.units.get(f"gov.{cc}")
        nat = re.compile(r"^gov\." + re.escape(cc) + r"\.[a-z0-9.-]+$")
        bodies, subdivisions = {}, 0
        coord_units = {a.get(":gov.address/unit") for a in self.addrs.values()
                       if a.get(":gov.address/lat") is not None}
        geocoded = 0
        for uid, u in self.units.items():
            if not nat.match(uid) or u is country:
                continue
            lvl = _kw(u.get(":gov.unit/level"))
            if lvl == "subdivision":
                subdivisions += 1
                continue
            bodies.setdefault(_kw(u.get(":gov.unit/branch")) or "—", []).append(u)
            if uid in coord_units:
                geocoded += 1
        return {"country": country, "bodies_by_branch": bodies,
                "national_body_count": sum(len(v) for v in bodies.values()),
                "subdivision_count": subdivisions, "geocoded_bodies": geocoded}

    # ── findService / resolveProcedure ───────────────────────────────────────
    def _addr(self, aid):
        a = self.addrs.get(aid)
        return {"id": aid, "postal": a.get(":gov.address/postal-code"),
                "line": a.get(":gov.address/line-local")} if a else None

    def _window(self, wid):
        w = self.windows.get(wid)
        if not w:
            return {"id": wid, "resolved": False}
        return {"id": wid, "name": w.get(":gov.window/name-local"),
                "address": self._addr(w.get(":gov.window/address")), "resolved": True}

    def _resolve(self, proc):
        u = self.units.get(proc.get(":gov.procedure/owner-unit"))
        return {
            "procedureId": proc[":gov.procedure/id"],
            "title": proc.get(":gov.procedure/title-local"),
            "toritsugiRef": proc.get(":gov.procedure/toritsugi-ref"),
            "owner": {"id": proc.get(":gov.procedure/owner-unit"),
                      "name": u.get(":gov.unit/name-local") if u else None},
            "legalBasis": proc.get(":gov.procedure/legal-basis"),
            "windows": [self._window(w) for w in (proc.get(":gov.procedure/window") or [])],
            "forms": [{"id": f, "chigiriRef": (self.forms.get(f) or {}).get(":gov.form/chigiri-ref")}
                      for f in (proc.get(":gov.procedure/form") or [])],
        }

    def resolve_procedure(self, toritsugi_ref):
        p = next((p for p in self.procs.values()
                  if p.get(":gov.procedure/toritsugi-ref") == toritsugi_ref), None)
        return self._resolve(p) if p else None

    def find_service(self, q):
        q = q.lower()
        return [self._resolve(p) for p in self.procs.values()
                if q in (p.get(":gov.procedure/title-local") or "").lower()
                or q in (p.get(":gov.procedure/toritsugi-ref") or "").lower()]


if __name__ == "__main__":
    import json
    import sys
    a = GovAtlas()
    if len(sys.argv) > 1:
        print(json.dumps(a.resolve_procedure(sys.argv[1]) or a.get_unit(sys.argv[1]),
                         ensure_ascii=False, indent=2))
    else:
        print(f"gov-atlas read client — {len(a.units)} units / {len(a.procs)} procedures "
              f"/ {len(a.windows)} windows (curated registry core)")
        print("  JP units:", len(a.by_jurisdiction("jpn")))
        print("  path(麹町税務署):", " → ".join(u.get(":gov.unit/name-local") for u in a.resolve_path("gov.jpn.mof.nta.tokyo.kojimachi")))
        print("  findService(住民票):", [r["owner"]["name"] for r in a.find_service("住民票")])
