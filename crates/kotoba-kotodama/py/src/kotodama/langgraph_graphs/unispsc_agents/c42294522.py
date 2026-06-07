from typing import TypedDict
from langgraph.graph import StateGraph, END

class PunctumPlugState(TypedDict):
    material_cert: str
    sterility_report: str
    compliance_status: bool

def validate_medical_cert(state: PunctumPlugState):
    return {'compliance_status': bool(state.get('material_cert') and state.get('sterility_report'))}

def route_procurement(state: PunctumPlugState):
    return 'approved' if state['compliance_status'] else 'rejected'

graph = StateGraph(PunctumPlugState)
graph.add_node('validate', validate_medical_cert)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
