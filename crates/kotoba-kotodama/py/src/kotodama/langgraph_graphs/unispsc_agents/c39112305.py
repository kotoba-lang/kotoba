from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class LightingState(TypedDict):
    specs: dict
    validation_errors: List[str]
    is_compliant: bool

async def validate_specs(state: LightingState):
    errors = []
    if not state['specs'].get('DMX_compatibility'):
        errors.append('Missing DMX compatibility specification.')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

async def finalize(state: LightingState):
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(LightingState)
graph.add_node('validate', validate_specs)
graph.add_node('finalizer', finalize)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalizer')
graph.add_edge('finalizer', END)
graph = graph.compile()
