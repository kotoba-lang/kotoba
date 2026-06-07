from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ServoState(TypedDict):
    servo_id: str
    spec_data: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: ServoState):
    # Simulate CAD/Spec validation for robotics component
    specs = state.get("spec_data", {})
    results = []
    if specs.get("latency_ms", 100) < 10:
        results.append("High-Speed Compliant")
    else:
        results.append("Latency Warning")
    return {"validation_results": results}

def check_compliance(state: ServoState):
    compliant = len(state.get("validation_results", [])) > 0
    return {"is_compliant": compliant}

graph = StateGraph(ServoState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
