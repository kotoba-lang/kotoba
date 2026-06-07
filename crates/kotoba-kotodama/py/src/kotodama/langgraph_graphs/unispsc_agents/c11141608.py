from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SiliconProcessingState(TypedDict):
    purity_level: float
    inspection_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_purity(state: SiliconProcessingState):
    purity = state.get('purity_level', 0.0)
    compliant = purity >= 99.9999
    return {'is_compliant': compliant, 'inspection_log': [f'Purity check: {purity}% - Compliant: {compliant}']}

def routing_step(state: SiliconProcessingState):
    if state['is_compliant']:
        return 'approve'
    return 'reject'

def approve_procurement(state: SiliconProcessingState):
    return {'inspection_log': ['Status: Approved for semiconductor fabrication.']}

def reject_procurement(state: SiliconProcessingState):
    return {'inspection_log': ['Status: Rejected. Purity standards not met.']}

graph = StateGraph(SiliconProcessingState)
graph.add_node('validate', validate_purity)
graph.add_node('approve', approve_procurement)
graph.add_node('reject', reject_procurement)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', routing_step, {'approve': 'approve', 'reject': 'reject'})
graph.add_edge('approve', END)
graph.add_edge('reject', END)
graph = graph.compile()
