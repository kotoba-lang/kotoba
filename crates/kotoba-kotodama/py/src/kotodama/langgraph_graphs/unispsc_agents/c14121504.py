from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    spec_data: dict
    validation_results: List[str]
    approved: bool

def validate_packaging_spec(state: PackagingState):
    spec = state.get('spec_data', {})
    results = []
    if spec.get('tensile_strength_mpa', 0) < 5:
        results.append('Insufficient tensile strength')
    return {'validation_results': results, 'approved': len(results) == 0}

workflow = StateGraph(PackagingState)
workflow.add_node('validate', validate_packaging_spec)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
