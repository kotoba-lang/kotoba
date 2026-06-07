from typing import TypedDict
from langgraph.graph import StateGraph, END

class ContainerState(TypedDict):
    spec_completed: bool
    compliance_passed: bool

def validate_specs(state: ContainerState):
    return {'spec_completed': True}

def check_compliance(state: ContainerState):
    return {'compliance_passed': True}

graph = StateGraph(ContainerState)
graph.add_node('val_spec', validate_specs)
graph.add_node('check_reg', check_compliance)
graph.set_entry_point('val_spec')
graph.add_edge('val_spec', 'check_reg')
graph.add_edge('check_reg', END)
graph = graph.compile()
