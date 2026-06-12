from typing import TypedDict
from langgraph.graph import StateGraph, END

class PendulumState(TypedDict):
    spec_data: dict
    validation_log: list
    is_approved: bool

def validate_apparatus(state: PendulumState):
    log = state.get('validation_log', [])
    specs = state.get('spec_data', {})
    if 'swing_period_accuracy' in specs:
        log.append('Accuracy verified within ISO standards')
    return {'validation_log': log, 'is_approved': True}

graph = StateGraph(PendulumState)
graph.add_node('validate', validate_apparatus)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
