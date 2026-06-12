from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GameProcurementState(TypedDict):
    title: str
    platform: str
    status: str
    validation_errors: List[str]

def validate_specs(state: GameProcurementState):
    errors = []
    if not state.get('platform'):
        errors.append('Platform is missing')
    return {'validation_errors': errors}

def finalize_procurement(state: GameProcurementState):
    return {'status': 'Approved' if not state['validation_errors'] else 'Rejected'}

graph = StateGraph(GameProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
