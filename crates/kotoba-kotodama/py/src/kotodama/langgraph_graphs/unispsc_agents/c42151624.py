from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalToolState(TypedDict):
    model_id: str
    iso_compliant: bool
    sterilization_validated: bool
    performance_metrics: dict

def validate_compliance(state: DentalToolState):
    # Business logic for dental instrument verification
    is_valid = state.get('iso_compliant', False) and state.get('sterilization_validated', False)
    return {'performance_metrics': {'valid': is_valid}}

def finalize_procurement(state: DentalToolState):
    return {'performance_metrics': {'status': 'READY_FOR_ORDER'}}

graph = StateGraph(DentalToolState)
graph.add_node('validate', validate_compliance)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
