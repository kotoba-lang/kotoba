"""Integrity: every factory_path in the 63-builtin seed must import cleanly.

Reads the SQL up-file, regex-extracts the factory_path values, and verifies
each one resolves to a callable. This is the test that catches a typo'd
dotted path BEFORE psql apply on prod.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3].parent
_SEED_SQL = _REPO_ROOT / "30-graph" / "graph-schema" / "sql_migrations" \
            / "20260509120000_seed_langgraph_builtin_63.up.sql"


_FACTORY_PATH_RE = re.compile(
    r"VALUES \('[^']+', \d+, \d+, '[^']+', \d+, 'py_factory', '([^']+)'"
)


@pytest.fixture(scope="module")
def factory_paths() -> list[str]:
    text = _SEED_SQL.read_text(encoding="utf-8")
    paths = _FACTORY_PATH_RE.findall(text)
    assert len(paths) == 63, f"expected 63 py_factory rows, got {len(paths)}"
    return paths


def test_all_63_factory_paths_resolve(factory_paths: list[str]):
    failed: list[tuple[str, str]] = []
    for ref in factory_paths:
        mod_name, _, attr = ref.partition(":")
        if not attr:
            attr = "build_graph"
        try:
            m = importlib.import_module(mod_name)
            fn = getattr(m, attr, None)
            if not callable(fn):
                failed.append((ref, "not callable"))
        except Exception as exc:
            failed.append((ref, f"{type(exc).__name__}: {exc}"))
    assert not failed, f"unresolvable factory paths: {failed}"


def test_seed_assistant_id_unique(factory_paths: list[str]):
    text = _SEED_SQL.read_text(encoding="utf-8")
    aids = re.findall(
        r"INSERT INTO vertex_langgraph_assistant.+VALUES \('([^']+)',",
        text,
    )
    assert len(aids) == 63
    assert len(set(aids)) == 63, "duplicate assistant_id in seed"
