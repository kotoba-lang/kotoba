"""RW-resident LangGraph deployment loader (ADR-2605080600 amendment).

Reads vertex_langgraph_deployment + vertex_langgraph_assistant rows from
RisingWave and registers compiled StateGraphs into the in-process registry.

Supported assistant kinds:

  py_factory  — assistant.factory_path points at a module exposing a
                callable (default attr ``build_graph``) that returns a
                compiled StateGraph. v1 path; works for the existing
                ~50 in-image graphs without modification.

  topology    — assistant.spec is a JSON document of the form

                  {
                    "state_keys": ["input", "echo", "length", ...],
                    "entry": "<node_id>",
                    "edges": [{"from": "<src>", "to": "<dst | END>"}, ...],
                    "conditional_edges": [
                      {"from": "<src>",
                       "router": "<dotted.path:fn>",   # py_primitive callable
                       "paths": {"<key>": "<node_id | END>", ...}}
                    ]
                  }

                ``state_keys`` declares the tracked dict keys. LangGraph's
                StateGraph uses the schema to drive its default reducer
                (per-key merge); a bare ``dict`` schema would full-overwrite
                state on each step, which is not what node implementations
                expect. Empirically verified against langgraph 0.2.

                Per-node bindings live in vertex_langgraph_assistant_node:
                one row per node_id with kind ('py_primitive' for v2) and
                ref (dotted path to a node callable taking state -> dict).

Behavior:
- Reads only deployments with status='active'.
- Skips assistant_ids already present in _GRAPH_REGISTRY when caller supplies
  an ``already_registered`` predicate (v1 additive rollout).
- Tolerates missing tables / pool errors: returns counters, never raises.
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
from typing import Any, Awaitable, Callable

LOG = logging.getLogger("langgraph_loader")

LoadResult = dict[str, int]
RegisterFn = Callable[[str, Any], None]


_SELECT_ACTIVE_SQL = """
SELECT d.assistant_id, d.version, a.kind, a.factory_path, a.spec, d.status, d.updated_at,
       COALESCE(a.checkpointer_mode, 'none') AS checkpointer_mode
FROM vertex_langgraph_deployment d
JOIN vertex_langgraph_assistant a
  ON a.assistant_id = d.assistant_id AND a.version = d.version
WHERE d.status = 'active'
"""

_SELECT_NODES_SQL = """
SELECT node_id, kind, ref, config
FROM vertex_langgraph_assistant_node
WHERE assistant_id = %s
"""


def _resolve_callable(dotted: str) -> Callable[..., Any]:
    """Import 'pkg.mod:attr' or 'pkg.mod' (defaults to ``build_graph``).

    Returns the callable itself; does NOT invoke it.
    """
    if ":" in dotted:
        module_name, attr = dotted.split(":", 1)
    else:
        module_name, attr = dotted, "build_graph"
    mod = importlib.import_module(module_name)
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise AttributeError(f"{dotted}: {attr} is not callable")
    return fn


def _resolve_factory(factory_path: str) -> Any:
    """Resolve a factory dotted path AND invoke it. Returns the compiled graph."""
    fn = _resolve_callable(factory_path)
    return fn()


def _resolve_checkpointer(mode: str | None) -> Any:
    """ADR-2605082100 — pick a LangGraph checkpointer for the given mode.

    Returns None for 'none' / unknown / on import failure. Failures are logged
    but never raised so a misconfigured row cannot block the loader.
    """
    if not mode or mode == "none":
        return None
    if mode in ("kotoba", "kotoba_datom"):
        try:
            from kotodama.langgraph_checkpoint_kotoba import KotobaCheckpointSaver
            return KotobaCheckpointSaver()
        except Exception as exc:
            LOG.warning("checkpointer kotoba init failed: %s", exc)
            return None
    if mode == "rw_vertex":
        import os
        if os.environ.get("KOTODAMA_LG_BACKEND", "kotoba") != "rw":
            try:
                from kotodama.langgraph_checkpoint_kotoba import KotobaCheckpointSaver
                return KotobaCheckpointSaver()
            except Exception as exc:
                LOG.warning("checkpointer rw_vertex (via kotoba fallback) init failed: %s", exc)
                return None
        try:
            from kotodama.langgraph_checkpoint_rw import RisingWaveCheckpointSaver
            return RisingWaveCheckpointSaver()
        except Exception as exc:
            LOG.warning("checkpointer rw_vertex init failed: %s", exc)
            return None
    if mode == "postgres":
        import os
        dsn = os.environ.get("HYPERDRIVE_LANGGRAPH_URL") or os.environ.get("DATABASE_URL")
        if not dsn:
            LOG.warning("checkpointer postgres requested but no DSN env var set")
            return None
        try:
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import-not-found]
            saver = PostgresSaver.from_conn_string(dsn)
            saver.setup()  # idempotent
            return saver
        except Exception as exc:
            LOG.warning("checkpointer postgres init failed: %s", exc)
            return None
    LOG.warning("unknown checkpointer_mode %r — defaulting to None", mode)
    return None


def _compile_topology(
    assistant_id: str,
    spec: dict,
    bindings: list[tuple],
    pool_factory: Callable[[], Awaitable[Any]] | None = None,
    checkpointer_mode: str | None = None,
    blob_fetcher: Callable[[str], Awaitable[bytes | None]] | None = None,
) -> Any:
    """Compile a StateGraph from a topology spec + node bindings.

    Args:
        spec: parsed topology JSON ({entry, edges, conditional_edges}).
        bindings: list of (node_id, kind, ref, config) rows from
            vertex_langgraph_assistant_node.

    Returns:
        Compiled langgraph StateGraph (callable graph object).
    """
    from typing import TypedDict
    from langgraph.graph import END, StateGraph

    state_keys = list(spec.get("state_keys") or [])
    if not state_keys:
        raise ValueError(
            f"{assistant_id}: topology spec missing 'state_keys' (required for per-key reducer)"
        )
    state_schema = TypedDict(  # type: ignore[misc]
        f"_State_{assistant_id}",
        {k: object for k in state_keys},
        total=False,
    )

    binding_by_id = {b[0]: b for b in bindings}
    referenced_ids: set[str] = set()
    referenced_ids.update(spec.get("entry") and [spec["entry"]] or [])
    for e in spec.get("edges", []) or []:
        if e.get("from"):
            referenced_ids.add(e["from"])
        if e.get("to") and e["to"] != "END":
            referenced_ids.add(e["to"])
    for ce in spec.get("conditional_edges", []) or []:
        if ce.get("from"):
            referenced_ids.add(ce["from"])
        for tgt in (ce.get("paths") or {}).values():
            if tgt and tgt != "END":
                referenced_ids.add(tgt)

    missing = referenced_ids - set(binding_by_id)
    if missing:
        raise ValueError(
            f"{assistant_id}: topology references node_ids without bindings: {sorted(missing)}"
        )

    builder = StateGraph(state_schema)

    for node_id, kind, ref, config in bindings:
        if node_id not in referenced_ids:
            # Orphan binding row — skip silently rather than fail.
            continue
        if kind == "py_primitive":
            fn = _resolve_callable(ref)
        else:
            from kotodama.langgraph_node_resolvers import resolve_node
            fn = resolve_node(
                kind, ref, config,
                pool_factory=pool_factory,
                blob_fetcher=blob_fetcher,
            )
        builder.add_node(node_id, fn)

    entry = spec.get("entry")
    if not entry:
        raise ValueError(f"{assistant_id}: topology spec missing 'entry'")
    builder.set_entry_point(entry)

    for e in spec.get("edges", []) or []:
        src = e["from"]
        dst = END if e["to"] == "END" else e["to"]
        builder.add_edge(src, dst)

    for ce in spec.get("conditional_edges", []) or []:
        router_path = ce.get("router")
        field = ce.get("field")
        condition_ref = ce.get("condition_ref")
        sources = sum(1 for s in (router_path, field, condition_ref) if s)
        if sources == 0:
            raise ValueError(
                f"{assistant_id}.{ce.get('from')}: conditional_edge missing one of "
                f"'router' / 'field' / 'condition_ref'"
            )
        if sources > 1:
            raise ValueError(
                f"{assistant_id}.{ce.get('from')}: conditional_edge has more than one of "
                f"'router' / 'field' / 'condition_ref' — pick exactly one (data-driven "
                f"'condition_ref' is preferred for policy-style decisions per "
                f"ADR-2604261100; 'field' for raw state dispatch per ADR-2605082000 Phase D)"
            )
        path_map = {
            key: (END if tgt == "END" else tgt)
            for key, tgt in (ce.get("paths") or {}).items()
        }
        if router_path:
            # Legacy py_primitive router (ADR-2605082000 §legacy compatibility).
            # Counted as routing-layer code-island by the audit script.
            router_fn = _resolve_callable(router_path)
        elif condition_ref:
            # Declarative policy routing (ADR-2604261100). The DMN row in
            # `vertex_dmn_model` is the SSoT; the runtime evaluator lives in
            # `kotodama.langgraph_node_resolvers`.
            if not condition_ref.startswith("dmn:"):
                raise ValueError(
                    f"{assistant_id}.{ce.get('from')}: unsupported condition_ref "
                    f"scheme {condition_ref!r} (only dmn:<key>@<version> is implemented)"
                )
            from kotodama.langgraph_node_resolvers import make_dmn_condition_router
            router_fn = make_dmn_condition_router(condition_ref, pool_factory)
        else:
            # Data-driven field-based routing (ADR-2605082000 Phase D).
            # `field` is a dotted path into state; resolved via the same
            # navigator as `tools.json.extract` / mcp_tool input_paths.
            # The runtime callable returns the value at that path verbatim,
            # which langgraph then dispatches via path_map.
            default_target = ce.get("default")  # optional: key when missing/unmatched
            field_path = field

            def _make_field_router(path: str, default: Any) -> Callable[[Any], Any]:
                def _router(state: Any) -> Any:
                    try:
                        from kotodama.tools_json_worker_main import _parse_path, _walk
                    except Exception:
                        return default
                    try:
                        tokens = _parse_path(path)
                    except ValueError:
                        return default
                    val = _walk(state, tokens)
                    return val if val is not None else default
                return _router

            router_fn = _make_field_router(field_path, default_target)
        builder.add_conditional_edges(ce["from"], router_fn, path_map)

    checkpointer = _resolve_checkpointer(checkpointer_mode)
    return builder.compile(checkpointer=checkpointer) if checkpointer else builder.compile()


async def _fetch_node_bindings(conn: Any, assistant_id: str) -> list[tuple]:
    cur = await conn.execute(_SELECT_NODES_SQL, (assistant_id,), prepare=False)
    return list(await cur.fetchall())


async def load_active_graphs(
    pool_factory: Callable[[], Awaitable[Any]],
    register_fn: RegisterFn,
    already_registered: Callable[[str], bool] | None = None,
) -> LoadResult:
    """Load all active deployments and register their graphs.

    Returns counters: loaded / skipped_existing / errors. The watcher-friendly
    snapshot ``seen`` (``{aid: (version, status, updated_at)}``) is also
    populated and accessible via ``result["seen"]`` so that the lifespan can
    pass it as ``initial_seen`` to ``langgraph_watcher.watch_forever``,
    avoiding a duplicate compile pass on first poll.
    """
    result: LoadResult = {"loaded": 0, "skipped_existing": 0, "errors": 0}
    seen: dict[str, tuple] = {}
    try:
        pool = await pool_factory()
    except Exception as exc:
        LOG.warning("load_active_graphs: pool unavailable, skipping: %s", exc)
        return result

    deploy_rows: list[tuple] = []
    try:
        async with pool.connection() as conn:
            # RW rejects PostgreSQL prepared statements; force unprepared.
            cur = await conn.execute(_SELECT_ACTIVE_SQL, prepare=False)
            deploy_rows = list(await cur.fetchall())
    except Exception as exc:
        LOG.warning("load_active_graphs: deployment query failed (table missing?): %s", exc)
        return result

    for row in deploy_rows:
        # checkpointer_mode column added in migration r_20260509130000 (ADR-2605082100).
        # Old test fixtures and pre-migration deployments may emit 7-tuple rows;
        # default to 'none' in that case.
        assistant_id, version, kind, factory_path, spec, status, updated_at = row[:7]
        checkpointer_mode = row[7] if len(row) > 7 else "none"
        seen[assistant_id] = (version, status, updated_at)
        try:
            if already_registered is not None and already_registered(assistant_id):
                result["skipped_existing"] += 1
                LOG.info(
                    "load_active_graphs: %s v%s already registered (in-image), skipping",
                    assistant_id, version,
                )
                continue

            if kind == "py_factory":
                if not factory_path:
                    raise ValueError("py_factory row missing factory_path")
                graph = _resolve_factory(factory_path)

            elif kind == "single_task":
                # 1-node graph wrapping a `task_*` coroutine. factory_path is
                # the dotted ref to the task callable (e.g.
                # "kotodama.kobo_worker_main:task_bud_agent"). State envelope
                # is the same SingleTaskState used by _single_task_wrapper.py.
                if not factory_path:
                    raise ValueError("single_task row missing factory_path")
                from kotodama.langgraph_graphs._single_task_wrapper import (
                    build_single_task_graph,
                )
                task_fn = _resolve_callable(factory_path)
                graph = build_single_task_graph(task_fn)

            elif kind == "topology":
                if not spec:
                    raise ValueError("topology row missing spec")
                spec_obj = json.loads(spec) if isinstance(spec, str) else spec
                async with pool.connection() as conn:
                    bindings = await _fetch_node_bindings(conn, assistant_id)
                if not bindings:
                    raise ValueError(
                        f"topology assistant {assistant_id!r} has no node bindings"
                    )
                graph = _compile_topology(
                    assistant_id, spec_obj, bindings,
                    pool_factory=pool_factory,
                    checkpointer_mode=checkpointer_mode,
                )

            else:
                LOG.warning(
                    "load_active_graphs: %s kind=%r not supported, skipping",
                    assistant_id, kind,
                )
                result["errors"] += 1
                continue

            register_fn(assistant_id, graph)
            result["loaded"] += 1
            LOG.info("load_active_graphs: registered %s v%s (kind=%s)", assistant_id, version, kind)

        except Exception as exc:
            LOG.warning("load_active_graphs: failed to register %s: %s", assistant_id, exc)
            result["errors"] += 1

    result["seen"] = seen  # type: ignore[assignment]
    LOG.info("load_active_graphs: %s (seen=%d)", {k: v for k, v in result.items() if k != "seen"}, len(seen))
    return result


# Re-export inspect helper for tests that want to assert sync/async wrapping.
def _is_async(fn: Callable[..., Any]) -> bool:
    return inspect.iscoroutinefunction(fn)
