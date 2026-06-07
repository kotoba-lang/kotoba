"""Tests for all gov_* country primitives + langgraph_registry + kotoba-kotodama_organizer."""

from __future__ import annotations

import asyncio
import importlib
import re
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest  # noqa: E402

# ─── langgraph_registry (pure, tiny) ─────────────────────────────────────────

from kotodama.primitives import langgraph_registry as LGR  # noqa: E402


def test_langgraph_register_and_get():
    LGR.register("test.graph.v1", object())
    assert LGR.get("test.graph.v1") is not None


def test_langgraph_get_missing_returns_none():
    assert LGR.get("does.not.exist.xyz") is None


def test_langgraph_list_ids_includes_registered():
    LGR.register("test.graph.v2", "dummy")
    ids = LGR.list_ids()
    assert "test.graph.v2" in ids


# ─── kotoba-kotodama_organizer ───────────────────────────────────────────────────────

from kotodama.primitives import kotoba-kotodama_organizer as MO  # noqa: E402


@pytest.fixture()
def _stub_mo_db():
    with patch("kotodama.primitives.kotoba-kotodama_organizer.sync_cursor") as m:
        cur = MagicMock()
        m.return_value.__enter__ = MagicMock(return_value=cur)
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield cur


def test_organizer_no_url_returns_error(_stub_mo_db):
    result = asyncio.run(MO.task_kotoba-kotodama_organizer_run(organizerUrl="", flush=False))
    assert result["ok"] is False
    assert "KOTODAMA_ORGANIZER_URL" in result["error"]
    assert result["auditUri"].startswith("at://")


def test_organizer_register_exposes_one_task():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    MO.register(FakeWorker(), timeout_ms=120_000)
    assert registered == ["kotoba-kotodama.organizer.run"]


# ─── gov_* modules — register() parametrized ─────────────────────────────────

# All 140 country codes
_GOV_COUNTRIES = [
    "afg", "ago", "alb", "and", "are", "arg", "atg", "aus", "aut", "bel",
    "bgd", "bgr", "bhr", "bih", "blr", "bol", "bra", "brb", "brn", "bwa",
    "can", "che", "chl", "chn", "civ", "cmr", "cod", "col", "cri", "cub",
    "cyp", "cze", "deu", "dma", "dnk", "dom", "dza", "ecu", "egy", "esp",
    "est", "eth", "fin", "fji", "fra", "gbr", "geo", "gha", "grc", "grd",
    "gtm", "guy", "hkg", "hnd", "hrv", "hti", "hun", "idn", "ind", "irl",
    "irn", "irq", "isl", "ita", "jam", "jor", "jpn", "kaz", "ken", "kgz",
    "khm", "kor", "kwt", "lao", "lbn", "lby", "lka", "ltu", "lux", "lva",
    "mar", "mdg", "mex", "mhl", "mkd", "mlt", "mmr", "mne", "mng", "moz",
    "mys", "nga", "nic", "nld", "nor", "npl", "nzl", "omn", "pak", "pan",
    "per", "phl", "png", "pol", "prk", "prt", "pry", "pse", "qat", "rou",
    "rus", "rwa", "sau", "sdn", "sen", "sgp", "slv", "srb", "ssd", "sur",
    "svk", "svn", "swe", "tha", "tjk", "tkm", "tls", "tur", "tza", "uga",
    "ukr", "ury", "usa", "uzb", "ven", "vnm", "yem", "zaf", "zmb", "zwe",
]


@pytest.mark.parametrize("country", _GOV_COUNTRIES)
def test_gov_register_exposes_tasks(country: str):
    """Each gov_* module must register ≥8 Zeebe tasks via register()."""
    mod = importlib.import_module(f"kotodama.primitives.gov_{country}")

    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    mod.register(FakeWorker(), timeout_ms=30_000)
    assert len(registered) >= 8, f"{country}: only {len(registered)} tasks registered"
    # Each task type should follow the xrpc.com.etzhayyim.gov{CC}.* pattern
    cc = country
    camel_cc = cc[0].upper() + cc[1:]  # e.g. "jpn" → "Jpn"
    prefix = f"xrpc.com.etzhayyim.gov{camel_cc}."
    for t in registered:
        assert t.startswith(prefix), f"{country}: task {t!r} doesn't match expected prefix {prefix!r}"


@pytest.mark.parametrize("country", _GOV_COUNTRIES)
def test_gov_primary_did_format(country: str):
    """Each gov_* module must set PRIMARY_DID in did:web:*-state.etzhayyim.com format."""
    mod = importlib.import_module(f"kotodama.primitives.gov_{country}")
    did = getattr(mod, "PRIMARY_DID", "")
    assert did.startswith("did:web:"), f"{country}: PRIMARY_DID={did!r} doesn't start with did:web:"
    assert "etzhayyim.com" in did, f"{country}: PRIMARY_DID={did!r} doesn't contain etzhayyim.com"


@pytest.mark.parametrize("country", ["jpn", "usa", "deu", "gbr", "fra"])
def test_gov_seed_orgs_task_exists(country: str):
    """A sample of gov modules must expose task_gov_{country}_seed_orgs."""
    mod = importlib.import_module(f"kotodama.primitives.gov_{country}")
    fn_name = f"task_gov_{country}_seed_orgs"
    assert hasattr(mod, fn_name), f"Missing {fn_name} in gov_{country}"
    fn = getattr(mod, fn_name)
    assert callable(fn)
