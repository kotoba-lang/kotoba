from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class NuclearMaterialState(TypedDict):
    material_id: str
    compliance_checks: Annotated[list[str], operator.add]
    is_approved: bool

def validate_composition(state: NuclearMaterialState):
    # Simulate material composition validation logic
    return {'compliance_checks': ['COMPOSITION_VALIDATED']}

def check_export_controls(state: NuclearMaterialState):
    # Simulate dual-use regulatory check
    return {'compliance_checks': ['EXPORT_CONTROL_PASSED']}

def final_approval(state: NuclearMaterialState):
    # Logic for final release to production
    return {'is_approved': True}

graph = StateGraph(NuclearMaterialState)
graph.add_node('validate', validate_composition)
graph.add_node('export', check_export_controls)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
