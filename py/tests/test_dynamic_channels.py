"""Regression tests for dynamic StateGraph(dict) channel semantics.

A `StateGraph(dict)` graph must match real LangGraph: the output state contains
only keys WRITTEN by a node (or carried from a prior checkpoint) — input-only
keys that no node writes are dropped. A typed-schema graph keeps its declared
channels unchanged. (ADR-2605312100 substrate fix.)
"""
from kotoba_langgraph import StateGraph, START, END, KotobaCheckpointer
from typing import Annotated, TypedDict
from kotoba_langgraph.messages import add_messages


def _dict_graph():
    def init(s):
        return {"work": {"projectId": s.get("projectId", "unknown"), "pct": 0}, "next_node": "emit"}
    def emit(s):
        return {"work": {**s.get("work", {}), "pct": 100}, "record": {"ok": True}, "next_node": "end"}
    g = StateGraph(dict)
    g.add_node("init", init); g.add_node("emit", emit)
    g.add_edge(START, "init"); g.add_edge("init", "emit"); g.add_edge("emit", END)
    return g.compile(checkpointer=KotobaCheckpointer())


def test_dynamic_drops_unwritten_input_key():
    out = _dict_graph().invoke({"projectId": "demo-001"})
    assert "projectId" not in out          # input-only, never written -> dropped
    assert set(out) == {"work", "record", "next_node"}
    assert out["work"]["projectId"] == "demo-001"   # still readable during execution


def test_dynamic_keeps_written_input_key():
    def bump(s):
        return {"count": s.get("count", 0) + 1, "next_node": "end"}
    g = StateGraph(dict)
    g.add_node("bump", bump)
    g.add_edge(START, "bump"); g.add_edge("bump", END)
    out = g.compile().invoke({"count": 5})
    assert out["count"] == 6               # input key IS written by node -> kept


def test_typed_schema_keeps_declared_input_channel():
    class S(TypedDict, total=False):
        projectId: str
        work: dict
        next_node: str
    def init(s):
        return {"work": {"pct": 100}, "next_node": "end"}
    g = StateGraph(S)
    g.add_node("init", init)
    g.add_edge(START, "init"); g.add_edge("init", END)
    out = g.compile().invoke({"projectId": "demo-001"})
    assert out["projectId"] == "demo-001"  # declared channel -> retained (langgraph parity)


def test_dynamic_keeps_prior_checkpoint_key():
    cp = KotobaCheckpointer()
    g = _dict_graph()
    g.invoke({"projectId": "p1"}, config={"configurable": {"thread_id": "T"}})
    # second turn on same thread: prior 'work'/'record' persist even if not re-written
    def noop(s):
        return {"next_node": "end"}
    g2 = StateGraph(dict)
    g2.add_node("noop", noop)
    g2.add_edge(START, "noop"); g2.add_edge("noop", END)
    out = g2.compile(checkpointer=cp).invoke({"seed": 1}, config={"configurable": {"thread_id": "T2"}})
    assert "seed" not in out               # input-only, unwritten -> dropped
    assert out["next_node"] == "end"
