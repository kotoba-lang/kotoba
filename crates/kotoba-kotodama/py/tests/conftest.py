"""Pytest configuration and shared stubs for kotodama test suite."""

from __future__ import annotations

import inspect
import sys
import types
from pathlib import Path as _P

# Make the real kotodama package importable before any test file runs.
_src = str(_P(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


def _install_langgraph_stub() -> None:
    """Stub langgraph.graph so agent modules load without the real package.

    Skip installation when the real langgraph (with checkpoint subpackage) is
    already importable — avoids shadowing the real namespace package.

    The stub supports add_node / add_edge / add_conditional_edges / compile,
    and the compiled graph implements ainvoke so tests that drive the graph
    end-to-end work correctly.
    """
    if "langgraph" in sys.modules:
        return

    # If the real langgraph package (with checkpoint) is available, skip stub.
    try:
        import importlib.util as _ilu
        if _ilu.find_spec("langgraph.checkpoint") is not None:
            return
    except (ModuleNotFoundError, ValueError):
        pass

    _END = "__end__"
    _START = "__start__"

    class _CompiledGraph:
        def __init__(self, nodes, regular_edges, cond_edges, entry):
            self._nodes = nodes
            self._regular_edges = regular_edges  # list of (src, dst)
            self._cond_edges = cond_edges        # list of (src, router_fn, mapping)
            self._entry = entry                  # explicit entry point (set_entry_point)

        def _resolve_next(self, current: str, state: dict) -> str:
            for src, router, mapping in self._cond_edges:
                if src == current:
                    res = router(state)
                    if isinstance(res, list): return res[0]
                    if isinstance(res, _Send): return res.node
                    if isinstance(mapping, dict): return mapping.get(res, res)
                    return res
            for src, dst in self._regular_edges:
                if src == current:
                    return dst
            return _END

        async def ainvoke(self, state: dict, config=None) -> dict:
            # We maintain a queue of (node_name, state_for_node)
            queue = []
            if self._entry:
                queue.append((self._entry, state))
            else:
                next_node = self._resolve_next(_START, state)
                queue.append((next_node, state))

            current_state = dict(state)
            visit_counts: dict[str, int] = {}
            MAX_VISITS = 50

            while queue:
                current, node_state = queue.pop(0)
                if current in (_END, None):
                    continue

                visit_counts[current] = visit_counts.get(current, 0) + 1
                if visit_counts[current] > MAX_VISITS:
                    break

                fn = self._nodes.get(current)
                if fn is not None:
                    if inspect.iscoroutinefunction(fn):
                        update = await fn(node_state)
                    else:
                        update = fn(node_state)
                        
                    if isinstance(update, dict):
                        # Simple merge for the mock (lists get appended)
                        for k, v in update.items():
                            if isinstance(v, list) and isinstance(current_state.get(k), list):
                                current_state[k] = current_state[k] + v
                            else:
                                current_state[k] = v

                # Evaluate outgoing edges from this node using current_state
                next_nodes = []
                # Check conditional edges first
                cond_matched = False
                for src, router, mapping in self._cond_edges:
                    if src == current:
                        cond_matched = True
                        res = router(node_state)
                        if isinstance(res, list):
                            for r in res:
                                if isinstance(r, _Send):
                                    queue.append((r.node, r.arg))
                                else:
                                    queue.append((r, current_state))
                        elif isinstance(res, _Send):
                            queue.append((res.node, res.arg))
                        else:
                            if isinstance(mapping, dict):
                                n = mapping.get(res, res)
                            else:
                                n = res
                            queue.append((n, current_state))
                        break
                        
                if not cond_matched:
                    # Regular edges
                    for src, dst in self._regular_edges:
                        if src == current:
                            queue.append((dst, current_state))
                            break

            print("DEBUG ainvoke return l1_results:", current_state.get("l1_results"))
            return current_state

    class _StateGraph:
        def __init__(self, schema=None):
            self._nodes: dict = {}
            self._regular_edges: list = []
            self._cond_edges: list = []
            self._entry: str | None = None

        def add_node(self, name, fn):
            self._nodes[name] = fn

        def add_edge(self, src, dst):
            self._regular_edges.append((src, dst))

        def add_conditional_edges(self, src, router, mapping=None):
            self._cond_edges.append((src, router, mapping or {}))

        def set_entry_point(self, node: str):
            self._entry = node

        def compile(self):
            return _CompiledGraph(
                self._nodes,
                self._regular_edges,
                self._cond_edges,
                self._entry,
            )

    class _Send:
        def __init__(self, node: str, arg: Any):
            self.node = node
            self.arg = arg

    langgraph_graph = types.ModuleType("langgraph.graph")
    langgraph_graph.StateGraph = _StateGraph  # type: ignore[attr-defined]
    langgraph_graph.END = _END  # type: ignore[attr-defined]
    langgraph_graph.START = _START  # type: ignore[attr-defined]
    
    langgraph_types = types.ModuleType("langgraph.types")
    langgraph_types.Send = _Send

    langgraph = types.ModuleType("langgraph")
    langgraph.graph = langgraph_graph  # type: ignore[attr-defined]
    langgraph.types = langgraph_types

    sys.modules["langgraph"] = langgraph
    sys.modules["langgraph.graph"] = langgraph_graph
    sys.modules["langgraph.types"] = langgraph_types


_install_langgraph_stub()
