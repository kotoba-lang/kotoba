from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class MailMachineState(TypedDict):
    model_id: str
    spec_check: bool
    approved: bool

def validate_specs(state: MailMachineState):
    # Simulate CAD/Spec validation for mail opener
    return {'spec_check': True}

def approval_flow(state: MailMachineState):
    return {'approved': True}

graph = StateGraph(MailMachineState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_flow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
