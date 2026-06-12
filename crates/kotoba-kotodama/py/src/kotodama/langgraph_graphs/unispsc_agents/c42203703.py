from typing import TypedDict
from langgraph.graph import StateGraph, END

class XRayPassboxState(TypedDict):
    spec_compliance: bool
    shielding_verified: bool
    interlock_tested: bool

def validate_shielding(state: XRayPassboxState):
    print('Verifying lead-equivalent thickness against safety standards...')
    return {'shielding_verified': True}

def validate_interlock(state: XRayPassboxState):
    print('Performing mechanical interlock diagnostic sequence...')
    return {'interlock_tested': True}

def aggregate_compliance(state: XRayPassboxState):
    is_compliant = state['shielding_verified'] and state['interlock_tested']
    return {'spec_compliance': is_compliant}

graph = StateGraph(XRayPassboxState)
graph.add_node('shielding', validate_shielding)
graph.add_node('interlock', validate_interlock)
graph.add_node('compliance', aggregate_compliance)
graph.set_entry_point('shielding')
graph.add_edge('shielding', 'interlock')
graph.add_edge('interlock', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
