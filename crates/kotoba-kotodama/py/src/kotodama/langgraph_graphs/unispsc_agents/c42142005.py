from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalInstrumentState(TypedDict):
    instrument_id: str
    compliance_report: dict
    is_approved: bool

def validate_instrument(state: SurgicalInstrumentState):
    # Simulate validation logic for needle holder specs
    return {"is_approved": True, "compliance_report": {"status": "passed"}}

def finalize_procurement(state: SurgicalInstrumentState):
    return {"compliance_report": {"final_status": "shippable"}}

graph = StateGraph(SurgicalInstrumentState)
graph.add_node("validate", validate_instrument)
graph.add_node("finalize", finalize_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
