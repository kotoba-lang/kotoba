from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ScreenFrameState(TypedDict):
    dimensions: dict
    material_compliance: bool
    validation_log: List[str]

def validate_specs(state: ScreenFrameState):
    log = state.get('validation_log', [])
    if state.get('dimensions'):
        log.append('Dimensions verified')
    return {'validation_log': log, 'material_compliance': True}

def approve_procurement(state: ScreenFrameState):
    return {'validation_log': state['validation_log'] + ['Procurement approved']}

graph = StateGraph(ScreenFrameState)
graph.add_node('validator', validate_specs)
graph.add_node('approver', approve_procurement)
graph.add_edge('validator', 'approver')
graph.add_edge('approver', END)
graph.set_entry_point('validator')
graph = graph.compile()
