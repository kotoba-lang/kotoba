from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SpellingResourceState(TypedDict):
    resource_id: str
    curriculum_level: str
    is_verified: bool
    validation_errors: List[str]

def validate_resource_content(state: SpellingResourceState):
    errors = []
    if not state.get('curriculum_level'):
        errors.append('Missing curriculum level specification')
    return {'validation_errors': errors, 'is_verified': len(errors) == 0}

def route_verification(state: SpellingResourceState):
    return 'verified' if state['is_verified'] else 'failed'

graph = StateGraph(SpellingResourceState)
graph.add_node('validate', validate_resource_content)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_verification, {'verified': END, 'failed': END})
graph = graph.compile()
