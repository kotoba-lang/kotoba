from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class ProcurementState(TypedDict):
    commodity_id: str
    quality_status: str
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: ProcurementState):
    # Simulate chemical purity validation logic
    return {'quality_status': 'Validated', 'validation_logs': ['Purity check passed at 99.9%']}

def check_storage(state: ProcurementState):
    # Simulate storage compliance check
    return {'validation_logs': ['Storage temperature verified within range']}

graph = StateGraph(ProcurementState)
graph.add_node('purity_check', validate_purity)
graph.add_node('storage_check', check_storage)
graph.add_edge('purity_check', 'storage_check')
graph.add_edge('storage_check', END)
graph.set_entry_point('purity_check')

graph = graph.compile()
