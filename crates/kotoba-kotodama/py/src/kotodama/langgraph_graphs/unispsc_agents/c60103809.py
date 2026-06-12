from typing import TypedDict
from langgraph.graph import StateGraph, END

class HistoryResourceState(TypedDict):
    content_metadata: dict
    validation_errors: list
    is_approved: bool

def validate_content(state: HistoryResourceState):
    errors = []
    if not state.get('content_metadata', {}).get('source_accreditation'):
        errors.append('Missing accreditation certification')
    return {'validation_errors': errors, 'is_approved': len(errors) == 0}

graph = StateGraph(HistoryResourceState)
graph.add_node('validate', validate_content)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
