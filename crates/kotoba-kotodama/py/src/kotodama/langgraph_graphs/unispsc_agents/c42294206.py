from langgraph.graph import StateGraph, END
from typing import TypedDict

class AuditState(TypedDict):
    instrument_list: list
    is_sterile: bool
    regulatory_compliant: bool

def validate_instruments(state: AuditState):
    return {'is_sterile': True}

def verify_compliance(state: AuditState):
    return {'regulatory_compliant': True}

graph = StateGraph(AuditState)
graph.add_node('validate', validate_instruments)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
