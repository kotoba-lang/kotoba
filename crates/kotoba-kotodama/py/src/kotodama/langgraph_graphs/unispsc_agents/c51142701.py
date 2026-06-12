from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    chemical_data: dict
    validation_report: dict

def validate_drug_compliance(state: ProcurementState):
    # Simulate regulatory validation for restricted pharmaceutical chemicals
    data = state.get('chemical_data', {})
    valid = data.get('purity', 0) >= 99.0
    return {'validation_report': {'status': 'approved' if valid else 'rejected'}}

def finalize_order(state: ProcurementState):
    return {'validation_report': {**state['validation_report'], 'order_id': 'PH-9921'}}

builder = StateGraph(ProcurementState)
builder.add_node('compliance', validate_drug_compliance)
builder.add_node('finalize', finalize_order)
builder.set_entry_point('compliance')
builder.add_edge('compliance', 'finalize')
builder.add_edge('finalize', END)
graph = builder.compile()
