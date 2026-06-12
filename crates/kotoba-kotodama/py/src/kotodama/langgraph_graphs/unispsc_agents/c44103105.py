from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class InkProcurementState(TypedDict):
    model_number: str
    is_compatible: bool
    yield_rating: float
    errors: List[str]

def validate_compatibility(state: InkProcurementState):
    # Simulate compatibility check logic
    if not state.get('model_number'):
        return {'errors': ['Missing model number']}
    return {'is_compatible': True}

def verify_specs(state: InkProcurementState):
    # Validate print yield standards
    if state.get('yield_rating', 0) < 100:
        return {'errors': ['Insufficient yield rating']}
    return {'errors': []}

workflow = StateGraph(InkProcurementState)
workflow.add_node('compatibility', validate_compatibility)
workflow.add_node('standards', verify_specs)
workflow.set_entry_point('compatibility')
workflow.add_edge('compatibility', 'standards')
workflow.add_edge('standards', END)
graph = workflow.compile()
