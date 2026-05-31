"""Pure-Python StateGraph — LangGraph-compatible graph builder and executor.

API is intentionally identical to ``langgraph.graph.StateGraph`` so that
users can swap the import and run inside a kotoba WASM component without
any pydantic / C-extension dependencies.

Reducers
--------
Channels declare a reducer via ``Annotated[T, reducer_fn]``.  The two
built-in reducers are:

  ``add_messages`` — appends messages (same semantics as LangGraph)
  ``operator.add`` — list concatenation (same semantics as LangGraph)

Any two-argument callable works as a reducer.

Example
-------
    from typing import Annotated, TypedDict
    from kotoba_langgraph import StateGraph, START, END
    from kotoba_langgraph.messages import add_messages

    class State(TypedDict):
        messages: Annotated[list, add_messages]

    def chatbot(state: State) -> dict:
        return {"messages": [{"role": "assistant", "content": "hi"}]}

    graph = StateGraph(State)
    graph.add_node("chatbot", chatbot)
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", END)

    compiled = graph.compile()
    result = compiled.invoke({"messages": [{"role": "user", "content": "hello"}]})
"""

from __future__ import annotations

import typing
from typing import Any, Callable, Optional, Union

START = "__start__"
END = "__end__"

# ── Reducer helpers ──────────────────────────────────────────────────────────

def _get_reducer(schema: type, key: str) -> Optional[Callable]:
    """Extract the reducer callable from an Annotated type hint, if present."""
    try:
        hints = typing.get_type_hints(schema, include_extras=True)
    except Exception:
        return None
    hint = hints.get(key)
    if hint is None:
        return None
    if typing.get_origin(hint) is not typing.Annotated:
        return None
    args = typing.get_args(hint)
    if len(args) >= 2 and callable(args[1]):
        return args[1]
    return None


def _apply_update(state: dict, update: dict, schema: type) -> None:
    for key, value in update.items():
        reducer = _get_reducer(schema, key)
        if reducer is not None:
            state[key] = reducer(state.get(key, []), value)
        else:
            state[key] = value


def _declared_channels(schema: type) -> Optional[set]:
    """Return the set of declared channel keys, or None for a dynamic (untyped)
    ``StateGraph(dict)`` schema.

    Real LangGraph keeps only *channel* values in the output state. For a typed
    schema the channels are its declared keys; for ``StateGraph(dict)`` there are
    no declared channels and the effective channel set is "keys some node writes"
    (input-only keys that no node writes are dropped from the output)."""
    try:
        hints = typing.get_type_hints(schema, include_extras=True)
    except Exception:
        hints = {}
    return set(hints) if hints else None


def _prune_dynamic_channels(state: dict, written: set, prior_keys: set) -> None:
    """For dynamic (``StateGraph(dict)``) graphs, drop keys that came only from the
    input and were never written by a node — matching real LangGraph, which never
    surfaces unwritten input keys in the output. Keys written by a node, or carried
    over from a prior checkpoint, are preserved."""
    for key in list(state):
        if key not in written and key not in prior_keys:
            del state[key]


# ── StateGraph ───────────────────────────────────────────────────────────────

class StateGraph:
    """LangGraph-compatible graph builder (pure Python, no pydantic).

    Parameters
    ----------
    state_schema:
        A ``TypedDict`` subclass whose fields declare channel types and
        optional reducers via ``Annotated[T, reducer_fn]``.
    """

    def __init__(self, state_schema: type) -> None:
        self._schema = state_schema
        self._nodes: dict[str, Callable] = {}
        self._edges: dict[str, str | Callable] = {}

    # ── Builder ──────────────────────────────────────────────────────────────

    def add_node(self, name: str, fn: Callable) -> "StateGraph":
        self._nodes[name] = fn
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        self._edges[source] = target
        return self

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable[[dict], str],
        path_map: Optional[dict[str, str]] = None,
    ) -> "StateGraph":
        if path_map:
            def _mapped(state: dict, _cond=condition, _map=path_map) -> str:
                return _map.get(_cond(state), END)
            self._edges[source] = _mapped
        else:
            self._edges[source] = condition
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        self._edges[START] = name
        return self

    def compile(
        self,
        checkpointer: Any = None,
        interrupt_before: Optional[list[str]] = None,
        interrupt_after: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> "CompiledGraph":
        return CompiledGraph(self, checkpointer)


# ── CompiledGraph ─────────────────────────────────────────────────────────────

class CompiledGraph:
    """Compiled, executable graph produced by ``StateGraph.compile()``.

    Matches ``CompiledStateGraph.invoke()`` / ``astream()`` semantics from
    LangGraph.  Single-threaded superstep execution (no parallel branches in
    Phase 1).
    """

    MAX_STEPS: int = 256

    def __init__(self, graph: StateGraph, checkpointer: Any = None) -> None:
        self._graph = graph
        self._checkpointer = checkpointer

    def invoke(
        self,
        input_state: dict,
        config: Optional[dict] = None,
        **kwargs: Any,
    ) -> dict:
        """Run the graph to completion and return the final state.

        Parameters
        ----------
        input_state:
            Initial channel values (e.g. ``{"messages": [...]}``)
        config:
            Optional config dict.  Recognised key:
            ``{"configurable": {"thread_id": str}}``.
        """
        config = config or {}
        thread_id: str = config.get("configurable", {}).get("thread_id", "default")

        # Load prior state from checkpointer (for multi-turn threads)
        state: dict = {}
        if self._checkpointer is not None:
            try:
                prior = self._checkpointer.load(thread_id)
                if prior:
                    state.update(prior)
            except Exception:
                pass

        # Channel-semantics bookkeeping: keys present before input (prior checkpoint)
        # are channels; in a dynamic StateGraph(dict) only node-written keys survive.
        prior_keys = set(state)
        written: set = set()

        # Apply initial input (using reducers)
        _apply_update(state, input_state, self._graph._schema)

        # Walk the graph
        _start_edge: Union[str, Callable, None] = self._graph._edges.get(START)
        node: Optional[str] = _start_edge(state) if callable(_start_edge) else _start_edge

        steps = 0
        while node and node != END and steps < self.MAX_STEPS:
            fn = self._graph._nodes.get(node)
            if fn is None:
                break

            update = fn(state)
            if update:
                written |= set(update)
                _apply_update(state, update, self._graph._schema)

            edge = self._graph._edges.get(node)
            if edge is None:
                break
            if callable(edge):
                node = edge(state)
            else:
                node = edge

            steps += 1

        # Faithful channel semantics: drop input-only, unwritten keys for dynamic
        # (StateGraph(dict)) graphs so the output matches real LangGraph.
        if _declared_channels(self._graph._schema) is None:
            _prune_dynamic_channels(state, written, prior_keys)

        # Persist state to checkpointer
        if self._checkpointer is not None:
            try:
                self._checkpointer.save(thread_id, state)
            except Exception:
                pass

        return state

    async def ainvoke(
        self,
        input_state: dict,
        config: Optional[dict] = None,
        **kwargs: Any,
    ) -> dict:
        """Async variant; delegates to invoke (componentize-py supports asyncio)."""
        return self.invoke(input_state, config=config, **kwargs)

    def stream(
        self,
        input_state: dict,
        config: Optional[dict] = None,
        stream_mode: str = "values",
        **kwargs: Any,
    ):
        """Yield state snapshots after each node (stream_mode='values')."""
        config = config or {}
        thread_id: str = config.get("configurable", {}).get("thread_id", "default")
        state: dict = {}
        if self._checkpointer is not None:
            try:
                prior = self._checkpointer.load(thread_id)
                if prior:
                    state.update(prior)
            except Exception:
                pass

        prior_keys = set(state)
        written: set = set()
        _apply_update(state, input_state, self._graph._schema)
        _se2: Union[str, Callable, None] = self._graph._edges.get(START)
        node: Optional[str] = _se2(state) if callable(_se2) else _se2
        dynamic = _declared_channels(self._graph._schema) is None

        steps = 0
        while node and node != END and steps < self.MAX_STEPS:
            fn = self._graph._nodes.get(node)
            if fn is None:
                break
            update = fn(state)
            if update:
                written |= set(update)
                _apply_update(state, update, self._graph._schema)
            if stream_mode == "values":
                snap = dict(state)
                if dynamic:
                    _prune_dynamic_channels(snap, written, prior_keys)
                yield snap
            edge = self._graph._edges.get(node)
            if edge is None:
                break
            node = edge(state) if callable(edge) else edge
            steps += 1

        if dynamic:
            _prune_dynamic_channels(state, written, prior_keys)

        if self._checkpointer is not None:
            try:
                self._checkpointer.save(thread_id, state)
            except Exception:
                pass


# ── MessagesState convenience ────────────────────────────────────────────────

class MessagesState(typing.TypedDict):
    """Pre-built state schema with a messages channel (same as LangGraph)."""
    messages: typing.Annotated[list, lambda a, b: a + (b if isinstance(b, list) else [b])]
