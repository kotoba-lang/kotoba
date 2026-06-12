from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    compliance_check: bool
    temp_log_verified: bool
    gmp_certified: bool

def validate_compliance(state: ProcurementState):
    state['compliance_check'] = True
    return {'compliance_check': True}

def verify_logistics(state: ProcurementState):
    state['temp_log_verified'] = True
    return {'temp_log_verified': True}

graph = StateGraph(ProcurementState)
graph.add_node("compliance", validate_compliance)
graph.add_node("logistics", verify_logistics)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "logistics")
graph.add_edge("logistics", END)
graph = graph.compile()
