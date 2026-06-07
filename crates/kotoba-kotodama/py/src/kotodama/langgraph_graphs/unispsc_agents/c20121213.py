from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ServoState(TypedDict):
    specs: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: ServoState):
    specs = state.get("specs", {})
    results = []
    if "input_voltage_range" not in specs: results.append("Missing voltage range")
    if "communication_protocol" not in specs: results.append("Missing protocol")
    return {"validation_results": results}

def check_compliance(state: ServoState):
    is_compliant = len(state.get("validation_results", [])) == 0
    return {"is_compliant": is_compliant}

builder = StateGraph(ServoState)
builder.add_node("validate", validate_specs)
builder.add_node("compliance_check", check_compliance)
builder.set_entry_point("validate")
builder.add_edge("validate", "compliance_check")
builder.add_edge("compliance_check", END)
graph = builder.compile()
