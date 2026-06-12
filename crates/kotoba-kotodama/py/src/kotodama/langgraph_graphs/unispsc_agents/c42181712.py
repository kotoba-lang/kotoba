from typing import TypedDict
from langgraph.graph import StateGraph, END

class EKGState(TypedDict):
    device_id: str
    compliance_docs: list
    calibration_status: bool

def validate_specs(state: EKGState):
    print(f'Validating EKG unit: {state.get("device_id")}')
    return {"calibration_status": True}

def check_regulations(state: EKGState):
    return {"compliance_docs": ["IEC-60601-2-27", "ISO-13485"]}

graph = StateGraph(EKGState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", check_regulations)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "validate")
graph.add_edge("validate", END)
graph = graph.compile()
