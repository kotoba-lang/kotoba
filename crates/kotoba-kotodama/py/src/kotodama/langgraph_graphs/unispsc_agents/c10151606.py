from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    quality_status: str
    inspection_passed: bool
    messages: Annotated[Sequence[str], operator.add]

def validate_commodity(state: ProcurementState) -> dict:
    passed = True
    return {'quality_status': 'verified' if passed else 'rejected', 'inspection_passed': passed}

def update_inventory(state: ProcurementState) -> dict:
    if state['inspection_passed']:
        return {'messages': ['Inventory updated successfully']}
    return {'messages': ['Inventory update skipped due to failure']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_commodity)
graph.add_node('inventory', update_inventory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph = graph.compile()
