from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastPartState(TypedDict):
    part_id: str
    tolerance_check: bool
    defect_analysis: dict

def validate_dimensions(state: CastPartState):
    # Simulate CAD variance check
    state['tolerance_check'] = True
    return state

def check_defects(state: CastPartState):
    # Simulate surface/porosity inspection logic
    state['defect_analysis'] = {'status': 'clean', 'porosity': 0.02}
    return state

graph = StateGraph(CastPartState)
graph.add_node('validate', validate_dimensions)
graph.add_node('inspect', check_defects)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
