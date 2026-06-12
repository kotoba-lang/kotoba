"""junkan.cld — automatic causal-loop-diagram discovery (no LoopSpec required).

ADR-2605290927. Given only the stock series, infer all sufficiently-confident
directional flow edges (hypothesis-only, G5) and enumerate the simple directed
cycles among them — that is the set of candidate feedback loops the world is
currently running, discovered rather than declared.

Pure stdlib. Cycles are bounded in length and deduplicated by their directed
edge-set so each loop is reported once (enumerated from its smallest member).
"""

from __future__ import annotations

from .flows import infer_flow
from .models import LoopSpec, StockSeries


def infer_adjacency(
    stock_series: list[StockSeries], min_conf: float, lag: int
) -> dict[str, set[str]]:
    """Directed adjacency: a -> b when a lagged flow a→b clears ``min_conf``."""
    series = {s.stock_id: s for s in stock_series}
    adj: dict[str, set[str]] = {sid: set() for sid in series}
    for a in series:
        for b in series:
            if a == b:
                continue
            e = infer_flow(a, b, series[a].levels, series[b].levels, lag=lag)
            if e is not None and e.confidence >= min_conf:
                adj[a].add(b)
    return adj


def find_cycles(adj: dict[str, set[str]], max_len: int) -> list[list[str]]:
    """Enumerate simple directed cycles (length 2..max_len), each once.

    Canonicalization: a cycle is only emitted when started from its smallest
    member (string order), and deduped by its directed edge-set.
    """
    cycles: list[list[str]] = []
    seen: set[frozenset[tuple[str, str]]] = set()

    def dfs(start: str, current: str, path: list[str]) -> None:
        if len(path) > max_len:
            return
        for nxt in sorted(adj.get(current, ())):
            if nxt == start and len(path) >= 2:
                edge_set = frozenset(zip(path, path[1:] + [start]))
                if edge_set not in seen:
                    seen.add(edge_set)
                    cycles.append(list(path))
            elif nxt not in path and nxt > start:
                dfs(start, nxt, path + [nxt])

    for s in sorted(adj):
        dfs(s, s, [s])
    return cycles


def discover_loops(
    stock_series: list[StockSeries],
    *,
    min_conf: float = 0.5,
    max_len: int = 3,
    lag: int = 1,
) -> list[LoopSpec]:
    """Discover candidate feedback loops directly from the stock series."""
    adj = infer_adjacency(stock_series, min_conf=min_conf, lag=lag)
    specs: list[LoopSpec] = []
    for cyc in find_cycles(adj, max_len=max_len):
        specs.append(LoopSpec(loop_id="auto:" + "~".join(cyc), stock_cycle=cyc))
    return specs
