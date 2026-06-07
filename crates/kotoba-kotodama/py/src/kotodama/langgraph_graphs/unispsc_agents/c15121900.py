from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    resource_id: str
    quality_metrics: dict
    compliance_check: bool
    history: Annotated[Sequence[str], operator.add]

def validate_quality(state: MineralState) -> MineralState:
    metrics = state.get('quality_metrics', {})
    is_valid = metrics.get('purity_grade', 0) > 90
    return {'compliance_check': is_valid, 'history': ['Validated quality metrics']}

def route_procurement(state: MineralState) -> str:
    return 'COMPLIANT' if state['compliance_check'] else 'REJECT'

graph = StateGraph(MineralState)
graph.add_node('validate', validate_quality)
graph.add_edge('validate', 'route')
graph.add_node('route', lambda state: state)
graph.add_conditional_edges('route', route_procurement, {'COMPLIANT': END, 'REJECT': END})
graph.set_entry_point('validate')
graph = graph.compile()
