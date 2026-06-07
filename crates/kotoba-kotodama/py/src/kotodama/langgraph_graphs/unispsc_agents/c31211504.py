from typing import TypedDict
from langgraph.graph import StateGraph, END

class PaintProcureState(TypedDict):
    paint_type: str
    voc_compliance: bool
    sds_verified: bool
    approved: bool

def validate_paint_specs(state: PaintProcureState):
    # Business logic for paint validation
    is_compliant = state.get('voc_compliance', False) and state.get('sds_verified', False)
    return {'approved': is_compliant}

def route_by_approval(state: PaintProcureState):
    return 'approved_node' if state['approved'] else 'rejected_node'

graph = StateGraph(PaintProcureState)
graph.add_node('validate', validate_paint_specs)
graph.add_node('approved_node', lambda s: print('Material approved'))
graph.add_node('rejected_node', lambda s: print('Material rejected'))
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_approval)
graph.add_edge('approved_node', END)
graph.add_edge('rejected_node', END)
graph = graph.compile()
