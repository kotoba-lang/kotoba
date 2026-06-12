from typing import TypedDict
from langgraph.graph import StateGraph, END

class MacheteState(TypedDict):
    material_grade: str
    blade_hardness: int
    compliance_check: bool

def validate_specs(state: MacheteState):
    hardness = state.get('blade_hardness', 0)
    if 45 <= hardness <= 60:
        return {"compliance_check": True}
    return {"compliance_check": False}

def security_protocol(state: MacheteState):
    print("Triggering export control and security authorization workflow.")
    return {"compliance_check": state['compliance_check']}

graph = StateGraph(MacheteState)
graph.add_node("validate", validate_specs)
graph.add_node("security", security_protocol)
graph.set_entry_point("validate")
graph.add_edge("validate", "security")
graph.add_edge("security", END)
graph = graph.compile()
