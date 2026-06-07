from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabGlasswareState(TypedDict):
    specs: dict
    is_validated: bool

def validate_glassware(state: LabGlasswareState):
    specs = state.get('specs', {})
    # Check for mandatory technical certifications
    validated = 'Calibration Standard' in specs and 'Accuracy Class' in specs
    return {'is_validated': validated}

graph = StateGraph(LabGlasswareState)
graph.add_node('validate', validate_glassware)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
