from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    batch_id: str
    is_gmp_certified: bool
    compliance_check: bool

def validate_gmp(state: DrugProcurementState):
    return {'compliance_check': state.get('is_gmp_certified', False)}

def finalize_procurement(state: DrugProcurementState):
    return {'compliance_check': True} if state['compliance_check'] else {'compliance_check': False}

graph = StateGraph(DrugProcurementState)
graph.add_node('validate', validate_gmp)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
