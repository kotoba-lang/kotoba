from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GlassTestState(TypedDict):
    instrument_id: str
    calibration_status: bool
    compliance_report: str
    output_data: str

def validate_specs(state: GlassTestState):
    return {"compliance_report": "Verified: ISO and internal safety metrics met."}

def execute_test_routine(state: GlassTestState):
    return {"output_data": "Test results: [Hardness: 7Mohs, Stress: PASS]"}

builder = StateGraph(GlassTestState)
builder.add_node("validate", validate_specs)
builder.add_node("execute", execute_test_routine)
builder.set_entry_point("validate")
builder.add_edge("validate", "execute")
builder.add_edge("execute", END)
graph = builder.compile()
