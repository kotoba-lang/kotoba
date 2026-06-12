from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SterilizationSpecState(TypedDict):
    material_cert: str
    iso_compliant: bool
    validation_logs: List[str]

def validate_material(state: SterilizationSpecState):
    if state.get('material_cert'):
        return {'validation_logs': ['Material validated']}
    return {'validation_logs': ['Material validation failed']}

def check_compliance(state: SterilizationSpecState):
    if state.get('iso_compliant'):
        return {'validation_logs': state['validation_logs'] + ['Compliance verified']}
    return {'validation_logs': state['validation_logs'] + ['Compliance failed']}

graph = StateGraph(SterilizationSpecState)
graph.add_node('material', validate_material)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('material')
graph.add_edge('material', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
