from typing import TypedDict
from langgraph.graph import StateGraph, END

class NetRepeaterState(TypedDict):
    spec_sheet: dict
    validation_status: bool
    compliance_risk: str

def validate_specs(state: NetRepeaterState):
    specs = state.get('spec_sheet', {})
    status = all(k in specs for k in ['speed', 'protocol'])
    return {'validation_status': status}

def check_compliance(state: NetRepeaterState):
    return {'compliance_risk': 'dual-use-check' if state['validation_status'] else 'manual-review'}

graph = StateGraph(NetRepeaterState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
