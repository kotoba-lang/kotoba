from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class MoldState(TypedDict):
    mold_id: str
    spec_check: bool
    is_validated: bool
    logs: List[str]
def validate_specs(state: MoldState):
    # Simulate material compliance check
    return {'spec_check': True, 'logs': ['Material: USP Class VI verified']}
def check_geometry(state: MoldState):
    # Simulate tolerance validation
    return {'is_validated': True, 'logs': ['Geometry: Within 0.01mm tolerance']}
graph = StateGraph(MoldState)
graph.add_node('validate', validate_specs)
graph.add_node('geometry', check_geometry)
graph.add_edge('validate', 'geometry')
graph.add_edge('geometry', END)
graph.set_entry_point('validate')
graph = graph.compile()
