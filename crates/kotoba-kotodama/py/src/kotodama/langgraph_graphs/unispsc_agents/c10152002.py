from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SeedProcurementState(TypedDict):
    seed_id: str
    germination_rate: float
    status: str
    logs: List[str]

def validate_quality(state: SeedProcurementState):
    rate = state.get('germination_rate', 0.0)
    if rate >= 85.0:
        return {'status': 'ACCEPTED', 'logs': ['Quality passed']}
    else:
        return {'status': 'REJECTED', 'logs': ['Quality failed']}

graph = StateGraph(SeedProcurementState)
graph.add_node('validate', validate_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
