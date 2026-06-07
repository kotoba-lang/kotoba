from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CopyCounterState(TypedDict):
    counter_id: str
    specs: dict
    is_validated: bool
    validation_log: List[str]

def validate_counter_specs(state: CopyCounterState):
    specs = state.get('specs', {})
    log = []
    if 'accuracy' in specs and specs['accuracy'] < 0.999:
        log.append('Low accuracy rating')
    return {'is_validated': len(log) == 0, 'validation_log': log}

def route_to_approval(state: CopyCounterState):
    return 'approved' if state['is_validated'] else 'rejected'

graph = StateGraph(CopyCounterState)
graph.add_node('validate', validate_counter_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
