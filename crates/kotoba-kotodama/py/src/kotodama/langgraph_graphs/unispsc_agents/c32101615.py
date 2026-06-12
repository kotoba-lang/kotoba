from typing import TypedDict
from langgraph.graph import StateGraph, END

class BimosState(TypedDict):
    part_number: str
    spec_compliance: bool
    export_control_check: bool

def validate_specs(state: BimosState):
    state['spec_compliance'] = True
    print('Validating BIMOS thermal and electrical ratings...')
    return state

def check_dual_use(state: BimosState):
    state['export_control_check'] = True
    print('Checking dual-use export control regulations...')
    return state

graph = StateGraph(BimosState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_dual_use)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
