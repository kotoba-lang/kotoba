from langgraph.graph import StateGraph, END
from typing import TypedDict

class BallProcurementState(TypedDict):
    specification: dict
    validation_results: list
    is_compliant: bool

def validate_specs(state: BallProcurementState):
    specs = state.get('specification', {})
    results = []
    if specs.get('weight', 0) < 410 or specs.get('weight', 0) > 450:
        results.append('Weight out of FIFA standards')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def final_approval(state: BallProcurementState):
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(BallProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
