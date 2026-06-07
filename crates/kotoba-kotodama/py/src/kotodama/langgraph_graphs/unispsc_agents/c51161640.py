from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    quality_docs: List[str]
    is_compliant: bool

def validate_quality_specs(state: ProcurementState):
    required = {'GMP', 'CoA', 'SDS'}
    state['is_compliant'] = all(doc in state['quality_docs'] for doc in required)
    return state

def route_by_compliance(state: ProcurementState):
    return 'process' if state['is_compliant'] else 'reject'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_quality_specs)
graph.add_edge('validate', 'route')
graph.add_conditional_edges('route', route_by_compliance, {'process': END, 'reject': END})
graph.set_entry_point('validate')

graph = graph.compile()
