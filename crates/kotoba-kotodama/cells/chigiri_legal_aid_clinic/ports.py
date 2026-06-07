"""
Concrete ports for ChigiriLegalAidClinicCell — wires the intake StateGraph
to kotoba (storage), the Public-Fund counsel registry, jurisdictionPolicy,
and the Murakumo inference fleet.

Per ADR-2605302200 / 2605302330 / 2605302345 + ADR-2605215000 (Murakumo-only)
+ ADR-2605262130 (kotoba EAVT). The cell stays pure; all I/O lives here.

CONSTITUTIONAL NOTES:
  - MurakumoTriagePort is a NON-ADVICE classifier. It calls the Murakumo
    fleet (LiteLLM 127.0.0.1:4000 → gemma) with a system prompt that
    forbids advice and constrains output to a label enum; the cell's
    `_assert_no_advice` re-validates. No commercial GPU; no kotoba-llm.
  - KotobaMstPort writes legalAidMatter records to kotoba EAVT; it never
    writes a fee/consideration field (G15 — none exists in the schema).
  - PublicFundCounselPort resolves a lawyer LICENSED in the matter
    jurisdiction, retained via Public Fund (G16); counsel is never
    adherent-paid.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional


# ── Murakumo fleet (ADR-2605215000) — the ONLY inference SSoT ──────────
MURAKUMO_BASE = os.environ.get("MURAKUMO_LITELLM_URL", "http://127.0.0.1:4000")
MURAKUMO_MODEL = os.environ.get("MURAKUMO_MODEL", "gemma3:4b")
MURAKUMO_KEY = os.environ.get("LITELLM_API_KEY", "")

# kotoba EAVT node (ADR-2605262130)
KOTOBA_URL = os.environ.get("KOTOBA_URL", "http://localhost:8077")
KOTOBA_TOKEN = os.environ.get("KOTOBA_TOKEN", "")

_TRIAGE_SYSTEM = (
    "You are a routing classifier for a free legal-aid intake desk. "
    "You DO NOT give legal advice, opinions, or analysis of the matter. "
    "Read the adherent's description and output EXACTLY ONE label from this "
    "list and NOTHING else: {labels}. If unsure, output 'other'. "
    "Never output a sentence, never advise, never cite law."
)


class MurakumoTriagePort:
    """Non-advice practice-area classifier over the Murakumo fleet.

    Returns one label string. The cell re-validates against the enum
    (`_assert_no_advice`, G14); this port additionally hard-truncates to a
    single token and refuses multi-sentence output before returning.
    """

    def __init__(self, base: str = MURAKUMO_BASE, model: str = MURAKUMO_MODEL,
                 key: str = MURAKUMO_KEY, timeout: int = 30):
        self.base, self.model, self.key, self.timeout = base, model, key, timeout

    def classify(self, summary_cid: Optional[str], labels: list[str],
                 summary_text: str = "") -> str:
        # The summary is the adherent's OWN words; we classify, never advise.
        sys_prompt = _TRIAGE_SYSTEM.format(labels=", ".join(labels))
        body = json.dumps({
            "model": self.model,
            "temperature": 0,
            "max_tokens": 4,  # a label is one token; refuse essays structurally
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": (summary_text or summary_cid or "")[:4000]},
            ],
        }).encode()
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        req = urllib.request.Request(
            self.base + "/v1/chat/completions", data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            j = json.load(r)
        out = (j["choices"][0]["message"]["content"] or "").strip().lower()
        # belt-and-suspenders G14: a label is a single bare token
        token = out.split()[0] if out.split() else "other"
        return token if token in {l.lower() for l in labels} else "other"


class KotobaMstPort:
    """Read intake records / write legalAidMatter records to kotoba EAVT."""

    def __init__(self, url: str = KOTOBA_URL, token: str = KOTOBA_TOKEN):
        self.url, self.token = url, token

    def _post(self, nsid: str, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(
            f"{self.url}/xrpc/{nsid}", data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    def get(self, uri: str) -> dict:
        # TODO: resolve the intake record by at:// uri via kotoba quad read.
        return {"uri": uri}

    def put(self, lexicon: str, record: dict) -> str:
        """Ingest a legalAidMatter entity into kotoba EAVT.

        Guard: this method refuses to write a record carrying any
        consideration field (G15) — defence in depth behind the schema.
        """
        forbidden = {"fee", "price", "amount", "cost", "tithe",
                     "sbtPrice", "paymentRef", "invoice", "billing"}
        if forbidden & set(record.keys()):
            raise ValueError(
                "G15 violation: legalAidMatter record carries a consideration "
                "field; the legal-aid lane charges the adherent nothing.")
        res = self._post("com.etzhayyim.apps.kotobase.kg.ingest", {
            "entity": {
                "id": f"matter/{record.get('adherentDid','?')}/{lexicon}",
                "type": "legal-aid-matter",
                "lexicon": lexicon,
                "record": record,
            },
        })
        return res.get("cid", res.get("entityCid", "at://kotoba/matter"))


class JurisdictionPolicyPort:
    """Lookup com.etzhayyim.chigiri.jurisdictionPolicy enableState."""

    def __init__(self, mst: KotobaMstPort):
        self.mst = mst

    def lookup(self, jurisdiction: str) -> Optional[dict]:
        # TODO: kotoba quad lookup by jurisdiction; R1 returns the seed of
        # the ADR-2605302200 §D4 enabled set (compensation + advice-unreserved
        # families; AT + US-state are verify-required, hence absent/disabled).
        enabled = {"jpn", "deu", "fra", "gbr", "kor", "aus", "ca-on", "che"}
        if jurisdiction in enabled:
            return {"jurisdiction": jurisdiction, "enableState": "enabled"}
        return {"jurisdiction": jurisdiction, "enableState": "verify-required"}


class PublicFundCounselPort:
    """Resolve an in-jurisdiction licensed lawyer retained via Public Fund.

    G16: license_jurisdiction MUST equal the matter jurisdiction (DE:
    Befähigung zum Richteramt; US: bar admission). Conflict check lives
    here too. Counsel is retained out of the Public Fund (Council Lv6+,
    ADR-2605192145) — never adherent-paid.
    """

    def __init__(self, registry: Optional[dict] = None):
        # registry: jurisdiction -> list[counsel dict]. Injected from the
        # Public-Fund-attested counsel roster; empty until counsel onboard.
        self.registry = registry or {}

    def conflict_clear(self, adherent_did: str, summary_cid: Optional[str]) -> bool:
        # TODO: check adverse-party overlap across open matters.
        return True

    def resolve(self, jurisdiction: str, practice_area: Optional[str]) -> Optional[dict]:
        for c in self.registry.get(jurisdiction, []):
            if c.get("license_jurisdiction") == jurisdiction:
                return {"did": c["did"], "license_jurisdiction": jurisdiction}
        return None  # no counsel → cell holds the matter at intake (G16)


def default_ports() -> dict:
    """Wire the standard production ports (env-configured)."""
    mst = KotobaMstPort()
    return {
        "mst_port": mst,
        "policy_port": JurisdictionPolicyPort(mst),
        "counsel_port": PublicFundCounselPort(),
        "murakumo_port": MurakumoTriagePort(),
    }
