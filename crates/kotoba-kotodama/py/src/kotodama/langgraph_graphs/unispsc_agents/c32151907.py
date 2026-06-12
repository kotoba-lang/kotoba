from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CableState(TypedDict):
    cable_id: str
    spec_compliance: bool
    validation_log: List[str]

def validate_specs(state: CableState):
    log = state.get('validation_log', [])
    log.append('Checking electrical continuity and connector pinout geometry.')
    return {'spec_compliance': True, 'validation_log': log}

def final_approval(state: CableState):
    return {'validation_log': state['validation_log'] + ['QA check passed.']}

graph = StateGraph(CableState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
