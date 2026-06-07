from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_passed: bool
    compliance_cleared: bool

def validate_coa(state: ProcurementState):
    # logic to verify Certificate of Analysis for Ergoloid mesylates
    print('Validating medical COA...')
    return {'quality_passed': True}

def check_regulatory(state: ProcurementState):
    # logic for pharma compliance
    print('Checking regulatory requirements...')
    return {'compliance_cleared': True}

workflow = StateGraph(ProcurementState)
workflow.add_node('verify_coa', validate_coa)
workflow.add_node('regulatory', check_regulatory)
workflow.set_entry_point('verify_coa')
workflow.add_edge('verify_coa', 'regulatory')
workflow.add_edge('regulatory', END)
graph = workflow.compile()
