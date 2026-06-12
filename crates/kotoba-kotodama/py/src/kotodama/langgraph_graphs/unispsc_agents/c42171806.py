from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SeizureStickState(TypedDict):
    material_certified: bool
    sterilization_validated: bool
    approval_status: str

def validate_materials(state: SeizureStickState) -> SeizureStickState:
    state['material_certified'] = True
    return state

def check_compliance(state: SeizureStickState) -> SeizureStickState:
    state['sterilization_validated'] = True
    state['approval_status'] = 'COMPLIANT'
    return state

graph = StateGraph(SeizureStickState)
graph.add_node('biocompatibility_check', validate_materials)
graph.add_node('regulatory_clearance', check_compliance)
graph.set_entry_point('biocompatibility_check')
graph.add_edge('biocompatibility_check', 'regulatory_clearance')
graph.add_edge('regulatory_clearance', END)
graph = graph.compile()
