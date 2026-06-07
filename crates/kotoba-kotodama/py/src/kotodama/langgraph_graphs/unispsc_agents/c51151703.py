from typing import TypedDict
from langgraph.graph import StateGraph, END

class EpinephrineState(TypedDict):
    batch_id: str
    expiry_check: bool
    gdp_compliant: bool

def validate_expiry(state: EpinephrineState):
    return {'expiry_check': True}

def verify_logistics(state: EpinephrineState):
    return {'gdp_compliant': True}

graph_builder = StateGraph(EpinephrineState)
graph_builder.add_node('validate_expiry', validate_expiry)
graph_builder.add_node('verify_logistics', verify_logistics)
graph_builder.set_entry_point('validate_expiry')
graph_builder.add_edge('validate_expiry', 'verify_logistics')
graph_builder.add_edge('verify_logistics', END)
graph = graph_builder.compile()
