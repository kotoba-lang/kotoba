from typing import TypedDict
from langgraph.graph import StateGraph, END

class MumpsMaterialState(TypedDict):
    material_id: str
    is_temperature_compliant: bool
    has_regulatory_approval: bool

def validate_cold_chain(state: MumpsMaterialState):
    return {'is_temperature_compliant': True}

def verify_regulatory_status(state: MumpsMaterialState):
    return {'has_regulatory_approval': True}

graph = StateGraph(MumpsMaterialState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('verify_regulatory_status', verify_regulatory_status)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'verify_regulatory_status')
graph.add_edge('verify_regulatory_status', END)
graph = graph.compile()
