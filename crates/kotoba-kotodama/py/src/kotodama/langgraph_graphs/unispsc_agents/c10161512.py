from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SeedProcurementState(TypedDict):
    seed_id: str
    quality_metrics: dict
    approved: bool
    logs: Annotated[Sequence[str], operator.add]

def validate_quality(state: SeedProcurementState):
    metrics = state.get('quality_metrics', {})
    approved = metrics.get('purity', 0) > 95 and metrics.get('germination', 0) > 85
    return {'approved': approved, 'logs': ['Quality validation completed']}

def route_by_approval(state: SeedProcurementState):
    return 'process_order' if state['approved'] else 'reject_order'

graph = StateGraph(SeedProcurementState)
graph.add_node('validate', validate_quality)
graph.add_node('process_order', lambda s: {'logs': ['Order sent to fulfillment']})
graph.add_node('reject_order', lambda s: {'logs': ['Order rejected, manual review required']})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_approval)
graph.add_edge('process_order', END)
graph.add_edge('reject_order', END)
graph = graph.compile()
