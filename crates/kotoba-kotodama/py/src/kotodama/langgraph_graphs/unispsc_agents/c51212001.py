from typing import TypedDict
from langgraph.graph import StateGraph, END

class OilProcurementState(TypedDict):
    purity_certified: bool
    msds_ready: bool
    procurement_approved: bool

def validate_compliance(state: OilProcurementState):
    return {'procurement_approved': state.get('purity_certified', False) and state.get('msds_ready', False)}

graph = StateGraph(OilProcurementState)
graph.add_node('validation', validate_compliance)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
