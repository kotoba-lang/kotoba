"""Node-kind resolvers for row-driven LangGraph topology compilation
(ADR-2605080600 v2 / P1b).

A resolver takes a (kind, ref, config) tuple from
``vertex_langgraph_assistant_node`` and returns an ``async (state) -> dict``
callable suitable for ``StateGraph.add_node``.

All resolvers share one ``config`` schema:

    {
      "input_keys": ["k1", "k2"],   // required
      "result_key": "k_out",        // required
      "args":       { ... }         // kind-specific
    }

Inputs are read from ``state[k]`` for each ``input_keys`` entry. The result
of the resolved op is written back to ``state[result_key]``.

Implemented kinds:

  py_primitive  (in langgraph_loader._compile_topology directly — not here)
  sql_udf       SELECT ref(args...) via shared psycopg AsyncConnectionPool.
                ref = SQL function name. ⚠ Per-row Python→RW roundtrip;
                use only for one-shot lookups, NOT per-row classification
                (see ADR-0044 D1 — that's plan-time inlining territory).
  py_ext_udf    Same wire path as sql_udf — Python External UDFs are exposed
                as SQL functions over Arrow Flight. Same caveat.
  mcp_tool      POST to an MCP endpoint with body = MCP ``tools/call`` envelope.
                ``ref`` can be one of:
                  - ``https://...`` (HTTP URL, legacy / explicit endpoint)
                  - ``mcp://<nsid>`` (registry-resolved per ADR-2605082000 §2.6 —
                    SELECT actor_host FROM vertex_mcp_tool_def WHERE nsid=$1
                    AND enabled=true; endpoint =
                    ``https://{actor_host}/xrpc/com.etzhayyim.mcp.message``;
                    tools/call ``name`` = nsid). Resolution requires ``pool_factory``,
                    cached in-process for 60 s.
  llm           kotodama.llm.call_tier_json(tier=ref, system+user from
                config, returns parsed JSON).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable

LOG = logging.getLogger("langgraph_node_resolvers")

# vertex_mcp_tool_def resolution cache: nsid -> (actor_host, expires_at_monotonic).
# 60s TTL matches the host-sdk in-memory cache convention (ADR-0087 / mcp-registry-loader.ts).
_MCP_REGISTRY_CACHE: dict[str, tuple[str, float]] = {}
_MCP_REGISTRY_TTL_S = 60.0
_MCP_NSID_PREFIX = "mcp://"
_MCP_ENVELOPE_PATH = "/xrpc/com.etzhayyim.mcp.message"

NodeFn = Callable[[dict], Awaitable[dict]]


# ---------------------------------------------------------------------------
# config helpers
# ---------------------------------------------------------------------------


def _parse_config(config: Any) -> dict:
    if config is None or config == "":
        return {}
    if isinstance(config, dict):
        return config
    return json.loads(config)


def _read_inputs(state: dict, keys: list[str]) -> list[Any]:
    return [state.get(k) for k in keys]


# ---------------------------------------------------------------------------
# sql_udf / py_ext_udf  (shared — both call SELECT fn(args))
# ---------------------------------------------------------------------------


def make_sql_udf_node(
    ref: str,
    config: Any,
    pool_factory: Callable[[], Awaitable[Any]],
) -> NodeFn:
    """Compile a SQL UDF reference into an async node callable.

    ref = SQL function name (e.g. ``classify_t1``).
    config = {"input_keys": [...], "result_key": "...", "args": {"prepare": false}}.
    """
    cfg = _parse_config(config)
    input_keys = list(cfg.get("input_keys") or [])
    result_key = cfg.get("result_key")
    if not result_key:
        raise ValueError(f"sql_udf {ref}: config missing 'result_key'")

    placeholders = ", ".join(["%s"] * len(input_keys))
    sql = f"SELECT {ref}({placeholders})"

    async def _node(state: dict) -> dict:
        params = tuple(_read_inputs(state, input_keys))
        pool = await pool_factory()
        async with pool.connection() as conn:
            cur = await conn.execute(sql, params, prepare=False)
            row = await cur.fetchone()
        return {result_key: row[0] if row else None}

    return _node


# ---------------------------------------------------------------------------
# mcp_tool
# ---------------------------------------------------------------------------


_MCP_NSID_OVERRIDE_ENV_PREFIX = "MCP_NSID_OVERRIDE_"


def _read_mcp_nsid_overrides() -> list[tuple[str, str]]:
    """Read `MCP_NSID_OVERRIDE_<key>=<base_url>` env vars at call time.

    `<key>` is an NSID prefix with dots replaced by underscores (the
    only env-var-safe representation). The base URL is used verbatim,
    `_MCP_ENVELOPE_PATH` is appended at lookup time. Longest prefix wins
    on conflict — `MCP_NSID_OVERRIDE_ai_etzhayyim_apps_mangaka_tools` beats
    `MCP_NSID_OVERRIDE_ai_etzhayyim_apps` for an mangaka tool NSID.

    Use case: ADR-2605111200 + Phase C activation — the lg-mangaka pod
    sets `MCP_NSID_OVERRIDE_ai_etzhayyim_apps_mangaka_tools=http://localhost:8000`
    so the topology Pregel's `mcp://com.etzhayyim.apps.mangaka.tools.*` calls
    short-circuit to the same pod's /xrpc/{nsid} server (
    `lg_mangaka.server._TOOL_NSID_TO_HANDLER`) without an external
    round-trip through the CF Worker.
    """
    import os
    overrides: list[tuple[str, str]] = []
    for k, v in os.environ.items():
        if not k.startswith(_MCP_NSID_OVERRIDE_ENV_PREFIX) or not v:
            continue
        prefix = k[len(_MCP_NSID_OVERRIDE_ENV_PREFIX):].replace("_", ".")
        overrides.append((prefix, v.rstrip("/")))
    # Longest prefix first so a more specific override wins.
    overrides.sort(key=lambda p: len(p[0]), reverse=True)
    return overrides


async def _resolve_mcp_nsid(
    nsid: str, pool_factory: Callable[[], Awaitable[Any]]
) -> str:
    """Resolve `mcp://<nsid>` → MCP envelope endpoint via vertex_mcp_tool_def.

    Returns the full POST URL (`https://{actor_host}/xrpc/com.etzhayyim.mcp.message`).
    Cached in-process for 60 s. Raises ValueError if the nsid is unknown
    or disabled.

    Resolution order:
      1. `MCP_NSID_OVERRIDE_<prefix>` env var matching the NSID (Phase C
         in-cluster short-circuit — see `_read_mcp_nsid_overrides`).
      2. `vertex_mcp_tool_def` row lookup, cached in-process for 60 s.
    """
    # Env-var overrides bypass DB + cache entirely so a pod re-deploy with
    # a tweaked override picks up immediately (no stale cache hold).
    for prefix, base_url in _read_mcp_nsid_overrides():
        if nsid == prefix or nsid.startswith(prefix + "."):
            return f"{base_url}{_MCP_ENVELOPE_PATH}"

    now = time.monotonic()
    cached = _MCP_REGISTRY_CACHE.get(nsid)
    if cached is not None and cached[1] > now:
        return f"https://{cached[0]}{_MCP_ENVELOPE_PATH}"

    pool = await pool_factory()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT actor_host FROM vertex_mcp_tool_def "
            "WHERE nsid = %s AND enabled = true LIMIT 1",
            (nsid,),
            prepare=False,
        )
        row = await cur.fetchone()
    if not row or not row[0]:
        raise ValueError(f"mcp_tool: unknown or disabled nsid {nsid!r}")
    actor_host = row[0]
    _MCP_REGISTRY_CACHE[nsid] = (actor_host, now + _MCP_REGISTRY_TTL_S)
    return f"https://{actor_host}{_MCP_ENVELOPE_PATH}"


def make_mcp_tool_node(
    ref: str,
    config: Any,
    *,
    pool_factory: Callable[[], Awaitable[Any]] | None = None,
) -> NodeFn:
    """Compile an MCP tool reference into an async node callable.

    ref = HTTP URL of the MCP endpoint (typically
          https://mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message)
          OR ``mcp://<nsid>`` for registry-resolved endpoints (ADR-2605082000 §2.6).
          When the ``mcp://`` prefix is used, ``pool_factory`` is required and
          ``config.args.name`` is auto-set to the nsid (override allowed).
    config = {"input_keys":  [...],   // top-level state keys
              "input_paths": {"argName": "fetchOut.body.items[0]", ...},  // nested state navigation
              "result_key":  "...",
              "args": {"name": "<tool_name>",
                       "headers": {"authorization": "..."}}}
    The state values for ``input_keys`` (top-level) and ``input_paths``
    (nested) become the ``arguments`` dict on the MCP ``tools/call``
    envelope. ``input_paths`` keys are the kwarg names; values are
    dotted paths walked against ``state`` (same grammar as
    ``com.etzhayyim.tools.json.extract``: ``a.b[2].c`` / ``a.*``).
    """
    cfg = _parse_config(config)
    input_keys = list(cfg.get("input_keys") or [])
    input_paths = dict(cfg.get("input_paths") or {})
    result_key = cfg.get("result_key")
    if not result_key:
        raise ValueError(f"mcp_tool {ref}: config missing 'result_key'")
    args_cfg = cfg.get("args") or {}

    is_registry_ref = ref.startswith(_MCP_NSID_PREFIX)
    nsid: str | None = None
    if is_registry_ref:
        nsid = ref[len(_MCP_NSID_PREFIX):]
        if not nsid:
            raise ValueError(f"mcp_tool {ref}: nsid is empty")
        if pool_factory is None:
            raise ValueError(
                f"mcp_tool {ref}: pool_factory required for registry resolution"
            )

    # For registry refs, default tool name = nsid (config.args.name override allowed).
    tool_name = args_cfg.get("name") or nsid
    if not tool_name:
        raise ValueError(f"mcp_tool {ref}: config.args.name required")
    headers = dict(args_cfg.get("headers") or {})
    headers.setdefault("content-type", "application/json")
    # Static defaults from config.args.* — anything other than the reserved
    # `name` / `headers` keys is merged into the envelope's `arguments`.
    # Use case: identity / no-op tools (com.etzhayyim.tools.const.echo) where the
    # payload is config-only (state-independent). State-derived values from
    # `input_keys` override static defaults when keys collide.
    static_args = {
        k: v for k, v in args_cfg.items() if k not in ("name", "headers")
    }

    async def _node(state: dict) -> dict:
        # httpx is already a transitive dep of langgraph; safe to import here.
        import httpx
        if is_registry_ref:
            assert nsid is not None and pool_factory is not None
            url = await _resolve_mcp_nsid(nsid, pool_factory)
        else:
            url = ref
        arguments = {**static_args}
        for k in input_keys:
            arguments[k] = state.get(k)
        # Nested-path input lookups (input_paths). Reuses the same safe
        # navigator as com.etzhayyim.tools.json.extract so the path grammar is
        # identical across the resolver and the JSON tool.
        if input_paths:
            try:
                from kotodama.tools_json_worker_main import _parse_path, _walk
            except Exception:
                _parse_path = None  # type: ignore[assignment]
                _walk = None  # type: ignore[assignment]
            for arg_name, path in input_paths.items():
                if not _parse_path or not _walk:
                    break
                try:
                    tokens = _parse_path(path)
                except ValueError:
                    arguments[arg_name] = None
                    continue
                arguments[arg_name] = _walk(state, tokens)
        envelope = {
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.post(url, json=envelope, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return {result_key: data}

    return _node


# ---------------------------------------------------------------------------
# llm
# ---------------------------------------------------------------------------


def make_llm_node(ref: str, config: Any) -> NodeFn:
    """Compile an LLM call reference into an async node callable.

    ref = tier name (passed to kotodama.llm.call_tier_json's ``tier`` arg —
          e.g. ``structured`` / ``general`` / explicit model id).
    config = {"input_keys": [...], "result_key": "...",
              "args": {"system": "...", "user_template": "...",
                       "max_tokens": 800, "temperature": 0.1}}
    ``user_template`` is formatted with ``state[k]`` substitutions for each
    input_key (Python str.format style).
    """
    cfg = _parse_config(config)
    input_keys = list(cfg.get("input_keys") or [])
    result_key = cfg.get("result_key")
    if not result_key:
        raise ValueError(f"llm {ref}: config missing 'result_key'")
    args_cfg = cfg.get("args") or {}
    system = args_cfg.get("system") or ""
    user_template = args_cfg.get("user_template") or "{}"
    max_tokens = int(args_cfg.get("max_tokens", 800))
    temperature = float(args_cfg.get("temperature", 0.1))

    async def _node(state: dict) -> dict:
        # Defer import so test envs that stub llm.py still load.
        import asyncio
        from kotodama.llm import call_tier_json
        kwargs = {k: state.get(k) for k in input_keys}
        try:
            user = user_template.format(**kwargs)
        except Exception:
            user = user_template
        # call_tier_json is sync; run in thread to keep node async-friendly.
        result = await asyncio.to_thread(
            call_tier_json, ref, system, user,
            max_tokens=max_tokens, temperature=temperature,
        )
        return {result_key: result}

    return _node


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# foreach  (ADR-2605082000 Phase D — topology operator, not a leaf tool)
# ---------------------------------------------------------------------------


def make_foreach_node(
    config: Any,
    *,
    pool_factory: Callable[[], Awaitable[Any]] | None = None,
) -> NodeFn:
    """Compile a foreach reference into an async node callable.

    config = {
      "items_path": "<dotted path into state>",  // grammar = json.extract
      "result_key": "<state key for collected outputs>",
      "item_key":   "<key the inner node reads per iteration>",  // default "item"
      "node": {
        "kind":   "mcp_tool" | "sql_udf" | "py_ext_udf" | "llm",
        "ref":    "<...>",
        "config": { ... }
      }
    }

    Iteration is sequential (asyncio-friendly but not concurrent — keeps
    side-effect order deterministic, which matches the supervisor-style
    `for write in result.get("db_writes")` pattern this is built for).

    Each iteration runs the inner node against
    ``{**state, item_key: <list_item>}`` and collects the *full* return
    dicts into ``state[result_key]`` as a list. The caller can fan-in
    via a follow-up ``transform.map`` / ``llm`` node if it needs
    aggregation.
    """
    cfg = _parse_config(config)
    items_path = cfg.get("items_path")
    if not items_path:
        raise ValueError("foreach: config missing 'items_path'")
    result_key = cfg.get("result_key")
    if not result_key:
        raise ValueError("foreach: config missing 'result_key'")
    item_key = cfg.get("item_key") or "item"
    inner = cfg.get("node")
    if not isinstance(inner, dict):
        raise ValueError("foreach: config.node must be an object")
    inner_kind = inner.get("kind")
    inner_ref = inner.get("ref") or ""
    inner_cfg = inner.get("config")
    if not inner_kind:
        raise ValueError("foreach: config.node.kind required")

    # Compile the inner node once at plan time. resolve_node validates
    # the inner kind and surfaces ValueError early if pool_factory is
    # missing for sql_udf / mcp_tool registry refs.
    inner_node: NodeFn = resolve_node(
        inner_kind, inner_ref, inner_cfg, pool_factory=pool_factory,
    )

    # Lazy import to keep the module loadable when tools_json_worker_main
    # isn't available (mirrors mcp_tool node's input_paths handling).
    def _navigate(state: dict, path: str) -> Any:
        try:
            from kotodama.tools_json_worker_main import _parse_path, _walk
        except Exception:
            return None
        try:
            tokens = _parse_path(path)
        except ValueError:
            return None
        return _walk(state, tokens)

    async def _node(state: dict) -> dict:
        items = _navigate(state, items_path)
        if items is None:
            return {result_key: []}
        if not isinstance(items, list):
            return {result_key: [], "__foreach_error": (
                f"items_path {items_path!r} resolved to {type(items).__name__}, expected list"
            )}
        results: list[Any] = []
        for it in items:
            sub_state = {**state, item_key: it}
            out = await inner_node(sub_state)
            results.append(out)
        return {result_key: results}

    return _node


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------


def resolve_node(
    kind: str,
    ref: str,
    config: Any,
    *,
    pool_factory: Callable[[], Awaitable[Any]] | None = None,
    blob_fetcher: Callable[[str], Awaitable[bytes | None]] | None = None,
) -> NodeFn:
    """Dispatch (kind, ref, config) → an async node callable.

    `blob_fetcher` is the per-application binary-store callback used by
    `kind="llm_vision"` to materialise `image_keys` into bytes. kotodama
    is unaware of B2 / R2 / IPFS / fs — the caller (mangaka, etc.) wires it.
    """
    if kind == "sql_udf" or kind == "py_ext_udf":
        if pool_factory is None:
            raise ValueError(f"{kind} requires pool_factory")
        return make_sql_udf_node(ref, config, pool_factory)
    if kind == "mcp_tool":
        # pool_factory is optional for plain HTTP refs but required for `mcp://<nsid>`.
        return make_mcp_tool_node(ref, config, pool_factory=pool_factory)
    if kind == "llm":
        return make_llm_node(ref, config)
    if kind == "llm_vision":
        return make_llm_vision_node(ref, config, blob_fetcher=blob_fetcher)
    if kind == "foreach":
        return make_foreach_node(config, pool_factory=pool_factory)
    raise NotImplementedError(f"unknown node kind: {kind!r}")


# ---------------------------------------------------------------------------
# llm_vision  (P10.1b — multimodal critic node)
# ---------------------------------------------------------------------------


def make_llm_vision_node(
    ref: str,
    config: Any,
    *,
    blob_fetcher: Callable[[str], Awaitable[bytes | None]] | None = None,
) -> NodeFn:
    """Compile a vision-LLM reference into an async node callable.

    ``ref``     model id / tier name (forwarded to
                ``kotodama.llm.call_tier_vision_json`` — common values:
                ``vision`` (default OpenAI gpt-4o-mini-vision) or an
                explicit model id).
    ``config``  ``{"input_keys": [...],   // text state keys merged into the user message
                   "image_keys": [...],   // dotted paths into state that resolve to
                                            //   either a single blob_key str or a list
                                            //   of blob_key strings (e.g.
                                            //   ``"renders[*].blobKey"``)
                   "result_key": "...",
                   "args": {"system": "...", "user_template": "...",
                            "max_tokens": 384, "temperature": 0.2,
                            "model": "<model id, optional>"}}``

    The node fetches each resolved blob key via ``blob_fetcher`` (required
    when ``image_keys`` is non-empty), base64-encodes the bytes, and
    forwards them to the vision call together with the formatted text
    prompt. The parsed JSON reply is written to ``state[result_key]``.
    """
    cfg = _parse_config(config)
    input_keys = list(cfg.get("input_keys") or [])
    image_keys = list(cfg.get("image_keys") or [])
    result_key = cfg.get("result_key")
    if not result_key:
        raise ValueError(f"llm_vision {ref}: config missing 'result_key'")
    args_cfg = cfg.get("args") or {}
    system = args_cfg.get("system") or ""
    user_template = args_cfg.get("user_template") or "{}"
    max_tokens = int(args_cfg.get("max_tokens", 384))
    temperature = float(args_cfg.get("temperature", 0.2))
    model_override = args_cfg.get("model")

    if image_keys and blob_fetcher is None:
        raise ValueError(
            f"llm_vision {ref}: blob_fetcher is required when image_keys is non-empty"
        )

    async def _node(state: dict) -> dict:
        # Walk every image_keys path and collect the resolved blob_key
        # strings. Two path shapes are supported:
        #
        #   1. plain dotted path (e.g. `selected.blobKey`) — handled by the
        #      shared `tools_json_worker_main._walk` navigator.
        #   2. per-element wildcard (e.g. `renders.*.blobKey`) — the segment
        #      before `*` resolves to a list; for each element we then walk
        #      the remaining segments. This is the only image-extraction
        #      shape the canonical compose_scene_3d topology needs (best-of-N
        #      vision critic over `renders[]`).
        from kotodama.tools_json_worker_main import _parse_path, _walk

        resolved_keys: list[str] = []
        for path in image_keys:
            if ".*." in path or path.endswith(".*"):
                # Split around the first `*` segment.
                before, _, after = path.partition(".*")
                after = after.lstrip(".")
                try:
                    head_tokens = _parse_path(before) if before else []
                    tail_tokens = _parse_path(after) if after else []
                except ValueError:
                    continue
                head = _walk(state, head_tokens) if head_tokens else state
                if not isinstance(head, list):
                    continue
                for element in head:
                    v = _walk(element, tail_tokens) if tail_tokens else element
                    if isinstance(v, str):
                        resolved_keys.append(v)
                continue

            try:
                tokens = _parse_path(path)
            except ValueError:
                continue
            val = _walk(state, tokens)
            if isinstance(val, str):
                resolved_keys.append(val)
            elif isinstance(val, list):
                for v in val:
                    if isinstance(v, str):
                        resolved_keys.append(v)

        images_b64: list[str] = []
        if resolved_keys:
            assert blob_fetcher is not None
            import base64
            for k in resolved_keys:
                blob = await blob_fetcher(k)
                if blob:
                    images_b64.append(base64.b64encode(blob).decode("ascii"))

        # Defer the LLM import so test envs that stub the vision call can
        # monkeypatch `kotodama.llm.call_tier_vision_json` before this
        # closure resolves it.
        from kotodama.llm import call_tier_vision_json

        kwargs = {k: state.get(k) for k in input_keys}
        try:
            user = user_template.format(**kwargs)
        except Exception:
            user = user_template

        import asyncio
        # `call_tier_vision_json` resolves the concrete model id from the
        # tier (`_VISION_TIER_OVERRIDES`); an explicit override flows
        # through the `extra` dict, mirroring the legacy `call_tier`
        # contract.
        extra = {"model": model_override} if model_override else None
        result = await asyncio.to_thread(
            call_tier_vision_json,
            ref,
            system,
            user,
            images_b64,
            max_tokens=max_tokens,
            temperature=temperature,
            extra=extra,
        )
        return {result_key: result}

    return _node


# ---------------------------------------------------------------------------
# dmn condition router  (P10.3b — declarative routing via vertex_dmn_model)
# ---------------------------------------------------------------------------


# `dmn:<decision_key>@<version>` → cached parsed row.
_DMN_REGISTRY_CACHE: dict[str, tuple[dict, float]] = {}
_DMN_REGISTRY_TTL_S = 60.0
_DMN_REF_PREFIX = "dmn:"


def _parse_dmn_ref(ref: str) -> tuple[str, int]:
    """``dmn:com.etzhayyim.policies.foo.bar@1.0.0`` → (``com.etzhayyim.policies.foo.bar``, 1).

    The minor / patch parts of the version are advisory only — DMN rows
    are keyed by ``decision_key`` + integer major version in
    ``vertex_dmn_model``.
    """
    if not ref.startswith(_DMN_REF_PREFIX):
        raise ValueError(f"dmn ref must start with 'dmn:': {ref!r}")
    body = ref[len(_DMN_REF_PREFIX):]
    if "@" in body:
        key, ver = body.rsplit("@", 1)
        major = ver.split(".", 1)[0] or "1"
        try:
            return key, int(major)
        except ValueError:
            raise ValueError(f"dmn ref version must be integer-major: {ref!r}")
    return body, 1


async def _resolve_dmn_ref(
    condition_ref: str,
    pool_factory: Callable[[], Awaitable[Any]],
) -> dict:
    """``dmn:<key>@<version>`` → parsed decision row from vertex_dmn_model.

    Returns ``{decision_key, version, inputs, outputs, rules, hit_policy}``
    where ``rules`` is a list of ``{id, inputEntries, outputEntries}`` dicts
    and ``inputs`` / ``outputs`` carry ``[{name, typeRef}, ...]``. Cached
    in-process for 60 s mirroring ``_resolve_mcp_nsid``. Raises ValueError
    when no active row exists.
    """
    decision_key, version = _parse_dmn_ref(condition_ref)
    cache_key = f"{decision_key}@{version}"
    now = time.monotonic()
    cached = _DMN_REGISTRY_CACHE.get(cache_key)
    if cached is not None and cached[1] > now:
        return cached[0]

    pool = await pool_factory()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT inputs_json, outputs_json, rules_json, hit_policy "
            "FROM vertex_dmn_model "
            "WHERE decision_key = %s AND version = %s AND status = 'active' "
            "LIMIT 1",
            (decision_key, version),
            prepare=False,
        )
        row = await cur.fetchone()
    if not row:
        raise ValueError(f"dmn ref: no active row for {condition_ref!r}")

    inputs_json, outputs_json, rules_json, hit_policy = row
    decision = {
        "decision_key": decision_key,
        "version": version,
        "inputs": json.loads(inputs_json) if inputs_json else [],
        "outputs": json.loads(outputs_json) if outputs_json else [],
        "rules": json.loads(rules_json) if rules_json else [],
        "hit_policy": (hit_policy or "FIRST").upper(),
    }
    _DMN_REGISTRY_CACHE[cache_key] = (decision, now + _DMN_REGISTRY_TTL_S)
    return decision


def _eval_dmn_input_entry(entry: Any, value: Any, state: dict) -> bool:
    """Evaluate one DMN inputEntry against an input value.

    Supported FEEL subset (covers ~all practical decision tables):

      ``-``                    → always matches (don't-care).
      ``< N`` / ``<= N``       → numeric comparison.
      ``> N`` / ``>= N``       → numeric comparison.
      ``== N`` / ``= N``       → numeric or string equality.
      bare literal ``N`` / ``"s"`` → equality.
      named ref ``< maxIter``  → looks up ``state["maxIter"]`` and compares.

    Anything else is treated as a non-match (conservative — better than
    matching a misspelled operator and routing silently to the wrong path).
    """
    if entry is None:
        return True
    if not isinstance(entry, str):
        return entry == value
    text = entry.strip()
    if text == "" or text == "-":
        return True

    for op in ("<=", ">=", "<", ">"):
        if text.startswith(op):
            rhs_raw = text[len(op):].strip()
            rhs = _coerce_operand(rhs_raw, state)
            try:
                lhs = float(value)
                rhs_f = float(rhs)
            except (TypeError, ValueError):
                return False
            if op == "<":
                return lhs < rhs_f
            if op == "<=":
                return lhs <= rhs_f
            if op == ">":
                return lhs > rhs_f
            return lhs >= rhs_f
    if text.startswith("=="):
        rhs = _coerce_operand(text[2:].strip(), state)
        return value == rhs
    if text.startswith("="):
        rhs = _coerce_operand(text[1:].strip(), state)
        return value == rhs

    # Bare literal — quoted string, number, or named ref.
    rhs = _coerce_operand(text, state)
    return value == rhs


def _coerce_operand(text: str, state: dict) -> Any:
    """Parse a DMN operand text → Python value.

    Quoted strings → str. Numeric literals → float. Bare identifiers →
    ``state[identifier]`` (this is how ``< maxIter`` works).
    """
    s = text.strip()
    if not s:
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        return float(s)
    except ValueError:
        # Identifier → state lookup
        return state.get(s)


def _eval_dmn_rule(
    rule: dict,
    inputs_meta: list[dict],
    state: dict,
) -> bool:
    """All inputEntries must match (AND semantics) for the rule to fire."""
    entries = rule.get("inputEntries") or []
    for entry, meta in zip(entries, inputs_meta):
        name = meta.get("name") if isinstance(meta, dict) else None
        value = state.get(name) if name else None
        if not _eval_dmn_input_entry(entry, value, state):
            return False
    return True


def make_dmn_condition_router(
    condition_ref: str,
    pool_factory: Callable[[], Awaitable[Any]] | None,
) -> Callable[[dict], Awaitable[str]]:
    """Build an async conditional-edge router that evaluates a DMN decision.

    Returns the first column of the matching rule's ``outputEntries`` —
    that's the path label langgraph dispatches against the
    ``conditional_edges[].paths`` map.

    Only FIRST hit policy is supported (the by-far dominant choice and the
    one our seeded rows use). Other hit policies raise.
    """
    if pool_factory is None:
        raise ValueError(
            f"dmn condition router {condition_ref!r}: pool_factory is required"
        )

    async def _router(state: dict) -> str:
        decision = await _resolve_dmn_ref(condition_ref, pool_factory)
        if decision["hit_policy"] != "FIRST":
            raise NotImplementedError(
                f"dmn {condition_ref!r}: hit policy {decision['hit_policy']!r} not supported"
            )
        for rule in decision["rules"]:
            if _eval_dmn_rule(rule, decision["inputs"], state):
                outputs = rule.get("outputEntries") or []
                if not outputs:
                    raise ValueError(
                        f"dmn {condition_ref!r}: matched rule {rule.get('id')!r} has no outputEntries"
                    )
                # First output column is the path label. Strip wrapping
                # quotes that come from DMN literal strings.
                raw = outputs[0]
                if isinstance(raw, str):
                    return raw.strip().strip('"').strip("'")
                return str(raw)
        raise ValueError(
            f"dmn {condition_ref!r}: no rule matched state keys "
            f"{sorted(state.keys())[:8]}{'…' if len(state) > 8 else ''}"
        )

    return _router
