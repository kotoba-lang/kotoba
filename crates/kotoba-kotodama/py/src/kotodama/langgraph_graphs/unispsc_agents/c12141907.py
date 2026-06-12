from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RareEarthState(TypedDict):
    commodity_code: str
    purity_check: bool
    compliance_docs: Sequence[str]
    approval_status: str

def validate_purity(state: RareEarthState):
    # Simulate high-precision chemical verification logic
    return {'purity_check': True}

def check_export_controls(state: RareEarthState):
    # Simulate dual-use export control screening
    return {'approval_status': 'COMPLIANT'}

workflow = StateGraph(RareEarthState)
workflow.add_node('verify', validate_purity)
workflow.add_node('export_check', check_export_controls)
workflow.set_entry_point('verify')
workflow.add_edge('verify', 'export_check')
workflow.add_edge('export_check', END)

graph = workflow.compile()
