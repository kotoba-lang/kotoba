from typing import TypedDict
from langgraph.graph import StateGraph, END

class IrDASoftwareState(TypedDict):
    compatibility_check: bool
    protocol_compliant: bool
    security_verified: bool

def validate_tech_specs(state: IrDASoftwareState):
    return {'compatibility_check': True}

def verify_regulatory(state: IrDASoftwareState):
    return {'protocol_compliant': True, 'security_verified': True}

graph = StateGraph(IrDASoftwareState)
graph.add_node('validate', validate_tech_specs)
graph.add_node('regulatory', verify_regulatory)
graph.add_edge('validate', 'regulatory')
graph.add_edge('regulatory', END)
graph.set_entry_point('validate')
graph = graph.compile()
