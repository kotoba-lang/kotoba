from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FrameState(TypedDict):
    specs: dict
    validation_result: bool
    errors: List[str]

def validate_materials(state: FrameState):
    specs = state.get('specs', {})
    errors = []
    if 'wood_type' not in specs:
        errors.append('Missing wood material specification')
    return {'validation_result': len(errors) == 0, 'errors': errors}

def finalize_procurement(state: FrameState):
    return {'validation_result': True}

graph = StateGraph(FrameState)
graph.add_node('validate', validate_materials)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
