# ADR — Retire the per-code UNSPSC Python agents (superseded by the clj `unspsc` actor)

- Status: Accepted (staged execution in progress)
- Date: 2026-06-17
- Scope: `crates/kotoba-kotodama/py` (this submodule, `etzhayyim/kotoba`)
- Supersedes the per-code generation pattern of ADR-2605171300

## Context

The UNSPSC domain was originally materialised in Python as **one generated
LangGraph agent file per commodity code** under
`crates/kotoba-kotodama/py/src/kotodama/langgraph_graphs/unispsc_agents/c{code}.py`
— **18,343 files, ~1.23M LOC**. They are not statically imported: the package
`__init__.py` is a one-line docstring, and modules are resolved at runtime by
`langgraph_graphs/dynamic_runner.py` (and the `unispsc_organism` / `xrpc.unispsc`
loaders) via `importlib.import_module(f"...c{code}")`.

This whole surface is now superseded by the Clojure actor
`com-junkawasaki/orgs/etzhayyim/root/20-actors/unspsc` (already merged to
`etzhayyim/root@main`, commit `ce26a8dd6b`): **one framework + one data table**
(`resources/unspsc-taxonomy.edn`, 18,342 codes) on the `com-junkawasaki/kotodama`
runtime — replacing 18,343 generated files with a single injected capability +
taxonomy. Inference is Murakumo-only (ADR-2605215000).

## Decision

Retire the Python UNSPSC surface in **staged, independently-reviewable steps**,
ordered leaf → root so the tree stays importable at every step.

### Dependency layers (retirement order)

| Layer | What | Files | Notes |
|---|---|---|---|
| **A — generated agents** | `langgraph_graphs/unispsc_agents/c*.py` | 18,343 (~1.23M LOC) | Pure generated artifacts. **No static importers.** Dynamically loaded. |
| **B — loaders / domain** | `organism/unispsc_organism.py`, `xrpc/unispsc.py`, `langgraph_graphs/dynamic_runner.py`, `langgraph_graphs/open_unispsc_*.py`, `primitives/open_unispsc.py`, `unispsc_capabilities/*` | ~13 | Hand-written. Resolve/execute per-code agents. |
| **C — core wiring** | `organism/__init__.py` (exports `UnispscOrganism`), `mcp_dispatch.py`, `langgraph_server_app.py`, `organism/cell_main.py`, `organism/fleet_cell_main.py`, `organism/post_sink.py`, `organism/testing/__init__.py`, `phenotype_agents/{__init__,_registry}.py` | 8 | Import/re-export Layer B. Decouple here last. |
| **D — tests** | `tests/**` referencing `unispsc` / `UnispscOrganism` | 15 | Re-point to a non-UNSPSC reference organism or delete with their target. |

### Why Layer A deletion is runtime-safe (Step 1)

`dynamic_runner.run_dynamic_workflow` already treats a missing per-code module as
the **normal** case:

```python
except ImportError:
    return {"ok": True, "result": {"status": "no_custom_agent_found"}}
```

Deleting all `c*.py` therefore degrades every code to `no_custom_agent_found`
without breaking imports or the loaders — exactly the intended end state (bespoke
Python agents replaced by the clj actor). Step 1 is the bulk (18,343 files) and is
fully reversible on a branch.

## Staged plan

1. **Step 1 (this branch) — delete Layer A.** `git rm` the 18,343 generated
   `c*.py`. Keep `unispsc_agents/__init__.py` so the package still resolves and
   the graceful-fallback path stays live. Verify the package imports and the
   loader returns `no_custom_agent_found`.
2. **Step 2 — retire Layer B loaders + Layer D tests** that exist only to drive
   per-code agents (`dynamic_runner`, `open_unispsc_*`, `xrpc.unispsc`,
   `unispsc_capabilities`, the `open_unispsc` primitive + its tests).
3. **Step 3 — decouple Layer C.** Drop `UnispscOrganism` from
   `organism/__init__`'s public exports; re-point `mcp_dispatch`,
   `langgraph_server_app`, `cell_main`, `fleet_cell_main`, `post_sink`,
   `phenotype_agents`, and the organism tests to a minimal non-UNSPSC reference
   organism (the generic `kotodama` lifecycle), then remove
   `organism/unispsc_organism.py`.
4. **Step 4 — sweep** remaining references (MCP `unispsc-isic-mcp`, cells
   `unispsc_registry` / `unispsc_agent_executor`, sqlmesh model,
   `unspsc_kotoba_transact.py`) and update docs.

## Consequences

- ~1.23M LOC removed in Step 1 alone; repo clone/index materially lighter.
- Single source of truth for UNSPSC becomes the clj actor's data table.
- Runtime behaviour for UNSPSC commodity execution is unchanged after Step 1
  (already `no_custom_agent_found` for codes without a bespoke agent; now uniform).
- Layers B–C are a real refactor (8 core modules + 15 tests) and are sequenced
  after the safe bulk deletion.
