from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    commodity_id: str
    batch_id: str
    temperature_logs: Annotated[Sequence[float], operator.add]
    is_compliant: bool

def validate_cold_chain(state: ReagentState):
    avg_temp = sum(state['temperature_logs']) / len(state['temperature_logs'])
    return {"is_compliant": 2.0 <= avg_temp <= 8.0}

def audit_expiry(state: ReagentState):
    # Mock logic for expiry validation
    return {"is_compliant": state['is_compliant'] and True}

graph = StateGraph(ReagentState)
graph.add_node("cold_chain_check", validate_cold_chain)
graph.add_node("expiry_check", audit_expiry)
graph.add_edge("cold_chain_check", "expiry_check")
graph.add_edge("expiry_check", END)
graph.set_entry_point("cold_chain_check")
graph = graph.compile()
