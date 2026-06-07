from typing import TypedDict
from langgraph.graph import StateGraph, END

class LogicState(TypedDict):
    part_number: str
    spec_compliance: bool
    export_control_check: bool

def validate_ecl_specs(state: LogicState):
    # Simulate high-speed logic parameter validation
    state['spec_compliance'] = True
    return state

def check_dual_use(state: LogicState):
    # Check against dual-use export control lists
    state['export_control_check'] = True
    return state

graph = StateGraph(LogicState)
graph.add_node('validate', validate_ecl_specs)
graph.add_node('export_review', check_dual_use)
graph.add_edge('validate', 'export_review')
graph.add_edge('export_review', END)
graph.set_entry_point('validate')
graph = graph.compile()
