from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssessmentState(TypedDict):
    isbn: str
    is_verified: bool
    compliance_score: float

def validate_resource(state: AssessmentState):
    # Simulate validation logic for assessment books
    if state.get('isbn') and len(state['isbn']) >= 10:
        return {'is_verified': True, 'compliance_score': 1.0}
    return {'is_verified': False, 'compliance_score': 0.0}

def finalize_order(state: AssessmentState):
    print(f'Finalizing procurement for ISBN: {state.get("isbn")}')
    return {'compliance_score': 1.0}

graph = StateGraph(AssessmentState)
graph.add_node('validate', validate_resource)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
