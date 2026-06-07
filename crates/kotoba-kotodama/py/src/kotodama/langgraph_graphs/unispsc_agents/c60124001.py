from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CorkProcurementState(TypedDict):
    thickness: float
    density: float
    is_compliant: bool
    validation_report: str

def validate_specs(state: CorkProcurementState):
    density = state.get('density', 0)
    is_compliant = 100 <= density <= 500
    return {'is_compliant': is_compliant, 'validation_report': 'Compliant' if is_compliant else 'Density out of range'}

graph = StateGraph(CorkProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
