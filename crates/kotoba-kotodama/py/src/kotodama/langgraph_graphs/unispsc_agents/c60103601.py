from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HistoryState(TypedDict):
    resource_id: str
    validation_passed: bool
    metadata: List[str]

def validate_academic_data(state: HistoryState):
    state['validation_passed'] = 'curator_id' in state.get('metadata', [])
    return {'validation_passed': state['validation_passed']}

def enrich_metadata(state: HistoryState):
    return {'metadata': state.get('metadata', []) + ['provenance_verified']}

graph = StateGraph(HistoryState)
graph.add_node('validate', validate_academic_data)
graph.add_node('enrich', enrich_metadata)
graph.set_entry_point('validate')
graph.add_edge('validate', 'enrich')
graph.add_edge('enrich', END)
graph = graph.compile()
