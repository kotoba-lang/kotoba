from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SoftwareProcurementState(TypedDict):
    software_name: str
    license_count: int
    system_requirements_met: bool
    validation_report: List[str]

def validate_system_specs(state: SoftwareProcurementState):
    # Simulate validation logic for audio software requirements
    state['system_requirements_met'] = True
    state['validation_report'] = ['OS compatibility verified', 'Audio engine stability confirmed']
    return state

def generate_procurement_order(state: SoftwareProcurementState):
    return {"validation_report": state['validation_report'] + ['Order ready for submission']}

graph = StateGraph(SoftwareProcurementState)
graph.add_node("validate", validate_system_specs)
graph.add_node("order", generate_procurement_order)
graph.add_edge("validate", "order")
graph.add_edge("order", END)
graph.set_entry_point("validate")
graph = graph.compile()
