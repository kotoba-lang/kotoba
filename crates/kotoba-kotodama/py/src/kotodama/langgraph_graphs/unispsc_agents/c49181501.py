from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class BilliardOrder(TypedDict):
    specs: dict
    approved: bool
    final_check: str

def validate_specs(state: BilliardOrder):
    specs = state.get('specs', {})
    is_valid = all(key in specs for key in ['dimensions', 'rebound'])
    print(f'Validating specs: {is_valid}')
    return {'approved': is_valid}

def finalize_order(state: BilliardOrder):
    return {'final_check': 'Ready for shipment'}

graph = StateGraph(BilliardOrder)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
