from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity: str
    quality_check_passed: bool
    logistics_ready: bool

def validate_quality(state: ProcurementState):
    print('Validating pomegranate freshness and brix levels...')
    return {'quality_check_passed': True}

def arrange_logistics(state: ProcurementState):
    print('Scheduling refrigerated transport...')
    return {'logistics_ready': True}

graph = StateGraph(ProcurementState)
graph.add_node('quality_check', validate_quality)
graph.add_node('logistics', arrange_logistics)
graph.set_entry_point('quality_check')
graph.add_edge('quality_check', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
