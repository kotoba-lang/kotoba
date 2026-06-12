"""Tests for worker_main registration functions and ingest_cron_start._parse_args.

Covers:
- houbun_worker_main.register_houbun_tasks
- site_common_crawl_worker_main.register_site_common_crawl_tasks
- vector_embedding_worker_main.register_vector_embedding_tasks
- ingest_cron_start._parse_args (argument parsing defaults)
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# pyzeebe is not installed in the test environment — inject a minimal stub
# so the worker_main modules can be imported without a running Zeebe cluster.
if "pyzeebe" not in sys.modules:
    _pyzeebe = types.ModuleType("pyzeebe")
    _pyzeebe.ZeebeWorker = object  # type: ignore[attr-defined]
    _pyzeebe.ZeebeClient = object  # type: ignore[attr-defined]
    _pyzeebe.create_insecure_channel = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["pyzeebe"] = _pyzeebe
    sys.modules["pyzeebe.worker"] = types.ModuleType("pyzeebe.worker")
    sys.modules["pyzeebe.channel"] = types.ModuleType("pyzeebe.channel")


# ─── Fake ZeebeWorker for registration tests ─────────────────────────────────

class _FakeWorker:
    """Records task registrations without touching Zeebe."""

    def __init__(self):
        self.registered: list[dict] = []

    def task(self, *, task_type: str, single_value: bool, timeout_ms: int, **kwargs):
        entry = {
            "task_type": task_type,
            "single_value": single_value,
            "timeout_ms": timeout_ms,
            **kwargs,
        }

        def decorator(fn):
            self.registered.append({**entry, "fn": fn.__name__})
            return fn

        return decorator

    def task_types(self) -> list[str]:
        return [e["task_type"] for e in self.registered]


# ─── houbun_worker_main ───────────────────────────────────────────────────────

from kotodama.houbun_worker_main import register_houbun_tasks  # noqa: E402


def test_houbun_register_includes_rw_health_probe():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "rw.health.probe" in w.task_types()


def test_houbun_register_includes_create_run():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.createRun" in w.task_types()


def test_houbun_register_includes_plan():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.egovJpn.plan" in w.task_types()


def test_houbun_register_includes_acquire_cursor():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.acquireCursor" in w.task_types()


def test_houbun_register_includes_fetch():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.egovJpn.fetch" in w.task_types()


def test_houbun_register_includes_write_graph():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.writeGraph" in w.task_types()


def test_houbun_register_includes_verify_visibility():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.verifyVisibility" in w.task_types()


def test_houbun_register_includes_advance_cursor():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.advanceCursor" in w.task_types()


def test_houbun_register_includes_complete_run():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert "houbun.completeRun" in w.task_types()


def test_houbun_register_total_task_count():
    w = _FakeWorker()
    register_houbun_tasks(w)
    assert len(w.registered) == 9


def test_houbun_register_single_value_false():
    w = _FakeWorker()
    register_houbun_tasks(w)
    for entry in w.registered:
        assert entry["single_value"] is False


# ─── site_common_crawl_worker_main ───────────────────────────────────────────

from kotodama.site_common_crawl_worker_main import register_site_common_crawl_tasks  # noqa: E402


def test_site_cc_register_includes_rw_health_probe():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "rw.health.probe" in w.task_types()


def test_site_cc_register_includes_create_run():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.createRun" in w.task_types()


def test_site_cc_register_includes_plan():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.plan" in w.task_types()


def test_site_cc_register_includes_acquire_cursor():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.acquireCursor" in w.task_types()


def test_site_cc_register_includes_run_phase():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.runPhase" in w.task_types()


def test_site_cc_register_includes_record_artifacts():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.recordArtifacts" in w.task_types()


def test_site_cc_register_includes_verify_visibility():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.verifyVisibility" in w.task_types()


def test_site_cc_register_includes_advance_cursor():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.advanceCursor" in w.task_types()


def test_site_cc_register_includes_complete_run():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert "site.commonCrawl.completeRun" in w.task_types()


def test_site_cc_register_total_task_count():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    assert len(w.registered) == 9


def test_site_cc_register_single_value_false():
    w = _FakeWorker()
    register_site_common_crawl_tasks(w)
    for entry in w.registered:
        assert entry["single_value"] is False


# ─── vector_embedding_worker_main ─────────────────────────────────────────────

from kotodama.vector_embedding_worker_main import register_vector_embedding_tasks  # noqa: E402


def test_vec_embed_register_includes_rw_health_probe():
    w = _FakeWorker()
    register_vector_embedding_tasks(w)
    assert "rw.health.probe" in w.task_types()


def test_vec_embed_register_includes_backfill_batch():
    w = _FakeWorker()
    register_vector_embedding_tasks(w)
    assert "vectorEmbedding.backfillBatch" in w.task_types()


def test_vec_embed_register_total_task_count():
    w = _FakeWorker()
    register_vector_embedding_tasks(w)
    assert len(w.registered) == 2


def test_vec_embed_register_single_value_false():
    w = _FakeWorker()
    register_vector_embedding_tasks(w)
    for entry in w.registered:
        assert entry["single_value"] is False


def test_vec_embed_backfill_timeout_is_large():
    w = _FakeWorker()
    register_vector_embedding_tasks(w)
    backfill = next(e for e in w.registered if e["task_type"] == "vectorEmbedding.backfillBatch")
    assert backfill["timeout_ms"] >= 300_000


# ─── ingest_cron_start._parse_args (default values) ──────────────────────────

from kotodama.ingest_cron_start import _parse_args  # noqa: E402


def test_parse_args_default_family():
    args = _parse_args.__wrapped__() if hasattr(_parse_args, '__wrapped__') else None
    # Use sys.argv patching
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.family == "houbun"
    finally:
        _sys.argv = old_argv


def test_parse_args_default_source_id():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.source_id == "egov-jpn"
    finally:
        _sys.argv = old_argv


def test_parse_args_default_mode():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.mode == "delta"
    finally:
        _sys.argv = old_argv


def test_parse_args_default_limit():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.limit == 1
    finally:
        _sys.argv = old_argv


def test_parse_args_default_dry_run_false():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.dry_run is False
    finally:
        _sys.argv = old_argv


def test_parse_args_dry_run_flag():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start", "--dry-run"]
        args = _parse_args()
        assert args.dry_run is True
    finally:
        _sys.argv = old_argv


def test_parse_args_custom_family():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start", "--family", "kakaku"]
        args = _parse_args()
        assert args.family == "kakaku"
    finally:
        _sys.argv = old_argv


def test_parse_args_default_max_articles():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.max_articles == 80
    finally:
        _sys.argv = old_argv


def test_parse_args_default_batch_size():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.batch_size == 200
    finally:
        _sys.argv = old_argv


def test_parse_args_shard_id_negative_default():
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["ingest_cron_start"]
        args = _parse_args()
        assert args.shard_id == -1
    finally:
        _sys.argv = old_argv
