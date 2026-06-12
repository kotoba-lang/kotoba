"""Pure-path tests for worker queue primitives.

Covers:
- primitives/public_malak_ads.py: task_queue_seed_runs (invalid seeds → skipped, no DB)
  and task_process_queue (patched cursor, empty claim → 0 processed)
- primitives/onion_crawl.py: task_queue_seeds (valid .onion seed fills cap, no _claim_stale_seeds call)
  and task_process_queue (empty runs list → pure return)
- primitives/os_messaging_open_channels.py: task_queue_seed_runs (patched cursor),
  task_process_queue (patched cursor)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import kotodama.primitives.public_malak_ads as PMA
import kotodama.primitives.onion_crawl as OC
import kotodama.primitives.os_messaging_open_channels as OSM


def _noop_cursor_mock() -> MagicMock:
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.description = []
    cur.rowcount = 0
    cm = MagicMock()
    cm.return_value.__enter__.return_value = cur
    cm.return_value.__exit__.return_value = False
    return cm


# ══════════════════════════════════════════════════════════════════════════════
# public_malak_ads
# ══════════════════════════════════════════════════════════════════════════════

def test_pma_queue_seed_invalid_platform_returns_dict() -> None:
    # Seeds with unknown platform are skipped without any DB call
    result = asyncio.run(PMA.task_queue_seed_runs(seeds=[{"platform": "unknown_platform", "queryValue": "test", "queryKind": "search"}]))
    assert isinstance(result, dict)


def test_pma_queue_seed_invalid_platform_all_skipped() -> None:
    result = asyncio.run(PMA.task_queue_seed_runs(seeds=[{"platform": "unknown_platform", "queryValue": "test", "queryKind": "search"}]))
    assert result["queued"] == 0
    assert result["skipped"] >= 1


def test_pma_queue_seed_has_runs_key() -> None:
    result = asyncio.run(PMA.task_queue_seed_runs(seeds=[{"platform": "unknown_platform"}]))
    assert "runs" in result
    assert isinstance(result["runs"], list)


def test_pma_process_queue_patched_returns_dict() -> None:
    from kotodama.db_sync import sync_cursor as _real
    PMA.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(PMA.task_process_queue())
        assert isinstance(result, dict)
    finally:
        PMA.sync_cursor = _real


def test_pma_process_queue_patched_zero_processed() -> None:
    from kotodama.db_sync import sync_cursor as _real
    PMA.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(PMA.task_process_queue())
        assert result["processed"] == 0
    finally:
        PMA.sync_cursor = _real


def test_pma_process_queue_has_completed_key() -> None:
    from kotodama.db_sync import sync_cursor as _real
    PMA.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(PMA.task_process_queue())
        assert "completed" in result
    finally:
        PMA.sync_cursor = _real


def test_pma_process_queue_has_runs_list() -> None:
    from kotodama.db_sync import sync_cursor as _real
    PMA.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(PMA.task_process_queue())
        assert isinstance(result["runs"], list)
    finally:
        PMA.sync_cursor = _real


# ══════════════════════════════════════════════════════════════════════════════
# onion_crawl
# ══════════════════════════════════════════════════════════════════════════════

def test_onion_crawl_queue_seeds_onion_url_returns_dict() -> None:
    # One valid .onion URL fills cap=1 → no _claim_stale_seeds DB call
    result = asyncio.run(OC.task_queue_seeds(seeds=["http://example.onion/"], limit=1))
    assert isinstance(result, dict)


def test_onion_crawl_queue_seeds_onion_url_queued_one() -> None:
    result = asyncio.run(OC.task_queue_seeds(seeds=["http://example.onion/"], limit=1))
    assert result["queued"] == 1


def test_onion_crawl_queue_seeds_has_runs() -> None:
    result = asyncio.run(OC.task_queue_seeds(seeds=["http://example.onion/"], limit=1))
    assert "runs" in result
    assert isinstance(result["runs"], list)


def test_onion_crawl_process_queue_empty_returns_dict() -> None:
    # Empty runs list → no DB call → pure return
    result = asyncio.run(OC.task_process_queue(runs=[]))
    assert isinstance(result, dict)


def test_onion_crawl_process_queue_empty_zero_processed() -> None:
    result = asyncio.run(OC.task_process_queue(runs=[]))
    assert result.get("processed", 0) == 0


def test_onion_crawl_process_queue_empty_has_failed_key() -> None:
    result = asyncio.run(OC.task_process_queue(runs=[]))
    assert "failed" in result


def test_onion_crawl_process_queue_invalid_items_returns_dict() -> None:
    # Items without valid .onion host → failed, no HTTP call
    result = asyncio.run(OC.task_process_queue(runs=[{"url": "", "host": "not.onion"}]))
    assert isinstance(result, dict)


def test_onion_crawl_process_queue_invalid_items_failed_count() -> None:
    result = asyncio.run(OC.task_process_queue(runs=[{"url": "", "host": "not.onion"}]))
    assert result.get("failed", 0) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# os_messaging_open_channels
# ══════════════════════════════════════════════════════════════════════════════

def test_osm_queue_seed_runs_empty_returns_dict() -> None:
    from kotodama.db_sync import sync_cursor as _real
    OSM.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(OSM.task_queue_seed_runs(seeds=[]))
        assert isinstance(result, dict)
    finally:
        OSM.sync_cursor = _real


def test_osm_queue_seed_runs_empty_zero_queued() -> None:
    from kotodama.db_sync import sync_cursor as _real
    OSM.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(OSM.task_queue_seed_runs(seeds=[]))
        assert result["queued"] == 0
    finally:
        OSM.sync_cursor = _real


def test_osm_queue_seed_runs_has_runs_key() -> None:
    from kotodama.db_sync import sync_cursor as _real
    OSM.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(OSM.task_queue_seed_runs(seeds=[]))
        assert "runs" in result
    finally:
        OSM.sync_cursor = _real


def test_osm_process_queue_patched_returns_dict() -> None:
    from kotodama.db_sync import sync_cursor as _real
    OSM.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(OSM.task_process_queue())
        assert isinstance(result, dict)
    finally:
        OSM.sync_cursor = _real


def test_osm_process_queue_patched_zero_processed() -> None:
    from kotodama.db_sync import sync_cursor as _real
    OSM.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(OSM.task_process_queue())
        assert result.get("processed", 0) == 0
    finally:
        OSM.sync_cursor = _real


def test_osm_process_queue_has_completed_key() -> None:
    from kotodama.db_sync import sync_cursor as _real
    OSM.sync_cursor = _noop_cursor_mock()
    try:
        result = asyncio.run(OSM.task_process_queue())
        assert "completed" in result
    finally:
        OSM.sync_cursor = _real
