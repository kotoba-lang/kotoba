from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material_certified: bool
    safety_check_passed: bool
    inspection_report: str

def validate_materials(state: CastingState):
    return {'material_certified': True}

def safety_compliance(state: CastingState):
    return {'safety_check_passed': True}

graph = StateGraph(CastingState)
graph.add_node('MaterialValidation', validate_materials)
graph.add_node('SafetyCompliance', safety_compliance)
graph.set_entry_point('MaterialValidation')
graph.add_edge('MaterialValidation', 'SafetyCompliance')
graph.add_edge('SafetyCompliance', END)
graph = graph.compile()
