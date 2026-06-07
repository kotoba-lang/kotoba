from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from operator import add

class CrudeOilState(TypedDict):
    batch_id: str
    purity_level: float
    safety_clearance: bool
    validation_logs: Annotated[List[str], add]

def inspect_crude_quality(state: CrudeOilState):
    # Simulate chemical validation
    is_safe = state.get('purity_level', 0) > 0.95
    return {'safety_clearance': is_safe, 'validation_logs': ['Quality inspection complete']}

def route_by_safety(state: CrudeOilState):
    return 'process' if state['safety_clearance'] else 'reject'

def process_inventory(state: CrudeOilState):
    return {'validation_logs': ['Inventory logged successfully']}

def reject_batch(state: CrudeOilState):
    return {'validation_logs': ['Batch rejected due to low purity']}

builder = StateGraph(CrudeOilState)
builder.add_node('inspect', inspect_crude_quality)
builder.add_node('process', process_inventory)
builder.add_node('reject', reject_batch)
builder.set_entry_point('inspect')
builder.add_conditional_edges('inspect', route_by_safety)
builder.add_edge('process', END)
builder.add_edge('reject', END)
graph = builder.compile()
