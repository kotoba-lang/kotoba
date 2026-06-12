from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BulkState(TypedDict):
    product_id: str
    inspection_passed: bool
    compliance_score: float
    logs: Annotated[Sequence[str], operator.add]

def validate_batch(state: BulkState):
    # Simulate inspection logic
    return {'inspection_passed': True, 'logs': ['Batch integrity verified']}

def update_compliance(state: BulkState):
    return {'compliance_score': 0.95, 'logs': ['Compliance score updated']}

graph = StateGraph(BulkState)
graph.add_node('inspection', validate_batch)
graph.add_node('compliance', update_compliance)
graph.add_edge('inspection', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('inspection')
graph = graph.compile()
