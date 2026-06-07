from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OfficeFurnitureState(TypedDict):
    item_list: List[str]
    compliance_checked: bool
    approved: bool

def validate_specs(state: OfficeFurnitureState):
    print('Validating furniture dimensions and safety specs...')
    return {'compliance_checked': True}

def approval_flow(state: OfficeFurnitureState):
    print('Processing procurement approval for clerical furniture...')
    return {'approved': True}

graph = StateGraph(OfficeFurnitureState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_flow)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
