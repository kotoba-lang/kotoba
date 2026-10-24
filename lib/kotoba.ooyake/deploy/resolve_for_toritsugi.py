#!/usr/bin/env python3
"""ooyake 公 — toritsugi↔ooyake SSoT resolver (ADR-2606021600 + 2605312030).

Demonstrates the read-side SSoT consumption the ooyake manifest claims: given a
toritsugi procedureId (`:gov.procedure/toritsugi-ref`), resolve through the gov-atlas
to the WHO/WHERE/HOW toritsugi needs — 所管 unit + 住所, 窓口 + 住所, 書式 (→ chigiri
template), 法定処理期間 / 手数料 / 根拠法令, BPMN. This is the boundary in the manifest:
ooyake CATALOGS, toritsugi DELIVERS; the link is `:gov.procedure/toritsugi-ref`.

READ-SIDE only (G9): pure resolution over the ooyake registry seeds, no government
interaction, no mutation, offline, no fabrication. Run as a module for the demo +
assertions, or import `resolve(toritsugi_ref)`.

    python3 resolve_for_toritsugi.py            # demo + self-test
    python3 resolve_for_toritsugi.py <ref>      # resolve one toritsugi-ref
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))
SEEDS = [os.path.join(_REG, "gov-units.seed.edn"),
         os.path.join(_REG, "gov-units.jp-central.seed.edn"),
         os.path.join(_REG, "gov-units.toritsugi-procedures.seed.edn"),
         os.path.join(_REG, "gov-procedures.bpmn.edn")]


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
        if c == '"':
            return rs()
        if c == "{":
            return rm()
        if c == "[":
            return rv()
        return ra()

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
        if t == "true":
            return True
        if t == "false":
            return False
        if t == "nil":
            return None
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


def _load():
    units, addrs, windows, forms, procs = {}, {}, {}, {}, {}
    procs_bpmn = {}
    for f in SEEDS:
        doc = parse_edn(open(f, encoding="utf-8").read())
        for u in doc.get(":units", []):
            units[u[":gov.unit/id"]] = u
        for a in doc.get(":addresses", []):
            addrs[a[":gov.address/id"]] = a
        for w in doc.get(":windows", []):
            windows[w[":gov.window/id"]] = w
        for fm in doc.get(":forms", []):
            forms[fm[":gov.form/id"]] = fm
        for p in doc.get(":procedures", []):
            procs[p[":gov.procedure/id"]] = p
        for pr in doc.get(":processes", []):
            procs_bpmn[pr[":bpmn/id"]] = pr
    return units, addrs, windows, forms, procs, procs_bpmn


def resolve(toritsugi_ref: str) -> dict | None:
    units, addrs, windows, forms, procs, procs_bpmn = _load()
    proc = next((p for p in procs.values() if p.get(":gov.procedure/toritsugi-ref") == toritsugi_ref), None)
    if proc is None:
        return None

    def unit_view(uid):
        u = units.get(uid)
        return {"id": uid, "name": u.get(":gov.unit/name-local") if u else None,
                "level": (u.get(":gov.unit/level") or "")[1:] if u else None} if u else {"id": uid, "name": None}

    def addr_view(aid):
        a = addrs.get(aid)
        return {"id": aid, "postal": a.get(":gov.address/postal-code"), "line": a.get(":gov.address/line-local"),
                "hours": a.get(":gov.address/hours")} if a else None

    def window_view(wid):
        w = windows.get(wid)
        if not w:
            return {"id": wid, "resolved": False}
        return {"id": wid, "name": w.get(":gov.window/name-local"),
                "channel": [c[1:] if isinstance(c, str) and c.startswith(":") else c for c in (w.get(":gov.window/channel") or [])],
                "address": addr_view(w.get(":gov.window/address")), "resolved": True}

    def form_view(fid):
        fm = forms.get(fid)
        return {"id": fid, "title": fm.get(":gov.form/title-local"), "chigiriRef": fm.get(":gov.form/chigiri-ref")} if fm else {"id": fid, "resolved": False}

    def bpmn_view(bpmn_id):
        # Resolve the :gov.procedure/bpmn id to the matching BPMN-as-edn process
        # (gov-procedures.bpmn.edn) and return a summary; None if no process is
        # defined. The STUB "bpmn.ooyake.find-service" never matches a real
        # process entry, so a stubbed procedure resolves to None here.
        pr = procs_bpmn.get(bpmn_id) if bpmn_id else None
        if not pr:
            return None
        return {"processId": pr.get(":bpmn/id"),
                "name": pr.get(":bpmn/name"),
                "nodeCount": len(pr.get(":bpmn/nodes") or {}),
                "flowCount": len(pr.get(":bpmn/flows") or {}),
                "legalBasis": pr.get(":bpmn/legal-basis"),
                "provenance": pr.get(":bpmn/provenance")}

    return {
        "toritsugiRef": toritsugi_ref,
        "procedureId": proc[":gov.procedure/id"],
        "title": proc.get(":gov.procedure/title-local"),
        "ownerUnit": unit_view(proc.get(":gov.procedure/owner-unit")),
        "legalBasis": proc.get(":gov.procedure/legal-basis"),
        "fee": proc.get(":gov.procedure/fee"),
        "statutoryDays": proc.get(":gov.procedure/statutory-days"),
        "channel": [c[1:] if isinstance(c, str) and c.startswith(":") else c for c in (proc.get(":gov.procedure/channel") or [])],
        "windows": [window_view(w) for w in (proc.get(":gov.procedure/window") or [])],
        "forms": [form_view(f) for f in (proc.get(":gov.procedure/form") or [])],
        "bpmn": bpmn_view(proc.get(":gov.procedure/bpmn")),
        "verificationStatus": (proc.get(":gov.procedure/verification-status") or "")[1:],
    }


def _self_test():
    r = resolve("jp-juminhyo-utsushi")
    assert r is not None, "jp-juminhyo-utsushi must resolve"
    assert r["procedureId"] == "proc.jpn.juminhyo-utsushi"
    assert r["ownerUnit"]["name"] == "新宿区", r["ownerUnit"]
    assert r["windows"][0]["resolved"] and "戸籍住民課" in r["windows"][0]["name"]
    assert r["windows"][0]["address"] and "歌舞伎町" in r["windows"][0]["address"]["line"]
    assert r["forms"][0]["chigiriRef"] == "chigiri:gov:jp-juminhyo:v0"
    assert r["legalBasis"].startswith("住民基本台帳法")
    # tax procedure routes to the national tax agency
    t = resolve("jp-kakutei-shinkoku-etax")
    assert t and t["ownerUnit"]["id"] == "gov.jpn.mof.nta"
    # all 6 toritsugi R0 procedures now resolve through the gov-atlas (6/6 coverage)
    for ref, owner in [("jp-juminhyo-utsushi", "gov.jpn.city.13104"),
                       ("jp-tennyu-todoke", "gov.jpn.city.13104"),
                       ("jp-kakutei-shinkoku-etax", "gov.jpn.mof.nta"),
                       ("jp-shussei-todoke", "gov.jpn.city.13104"),
                       ("jp-mynumber-card", "gov.jpn.city.13104"),
                       ("jp-jido-teate", "gov.jpn.city.13104")]:
        rr = resolve(ref)
        assert rr is not None, f"{ref} must resolve"
        assert rr["ownerUnit"]["id"] == owner, (ref, rr["ownerUnit"])
        assert rr["legalBasis"], (ref, "legal basis")
        assert rr["windows"] and rr["windows"][0]["resolved"], (ref, "window")
        # forms exist for all but the e-Tax filing (online, no paper 様式)
        if ref != "jp-kakutei-shinkoku-etax":
            assert rr["forms"] and rr["forms"][0].get("chigiriRef"), (ref, "form/chigiri ref")
        # BPMN: every toritsugi R0 procedure now resolves to a REAL process summary
        # (not None, not the "bpmn.ooyake.find-service" STUB string). The summary
        # carries the processId + node/flow counts + the same G5 legal-basis/provenance.
        b = rr["bpmn"]
        assert b is not None, (ref, "bpmn process summary must not be None")
        assert isinstance(b, dict), (ref, "bpmn must be a summary map, not a stub string")
        assert b.get("processId"), (ref, "bpmn summary must carry a processId")
        assert b["processId"] != "bpmn.ooyake.find-service", (ref, "STUB must be gone")
        assert b["processId"].startswith("bpmn.ooyake.proc.jpn."), (ref, b["processId"])
        assert b["nodeCount"] >= 2 and b["flowCount"] >= 1, (ref, b)
        assert b["legalBasis"], (ref, "bpmn summary must carry legal-basis (G5)")
        assert b["provenance"], (ref, "bpmn summary must carry provenance (G5)")
    # 児童手当 routes to its own 子ども家庭課 window (not the koseki window)
    assert resolve("jp-jido-teate")["windows"][0]["id"] == "madoguchi.gov.jpn.city.13104.kodomo"
    # unknown ref → None (no fabrication)
    assert resolve("does-not-exist") is None
    print("PASS resolve_for_toritsugi self-test (6/6 toritsugi procedures + miss)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(resolve(sys.argv[1]), ensure_ascii=False, indent=2))
    else:
        for ref in ("jp-juminhyo-utsushi", "jp-tennyu-todoke", "jp-kakutei-shinkoku-etax"):
            r = resolve(ref)
            w = r["windows"][0]
            print(f"{ref} → {r['title']} @ {r['ownerUnit']['name']} / 窓口 {w.get('name')} "
                  f"({(w.get('address') or {}).get('line')}) · 根拠 {r['legalBasis']}")
        _self_test()
