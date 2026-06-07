from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity: str
    quality_check_passed: bool
    logistics_ready: bool

def validate_freshness(state: ProcurementState):
    print('Validating pineapple ripeness and brix levels...')
    return {'quality_check_passed': True}

def manage_cold_chain(state: ProcurementState):
    print('Verifying temperature sensors for refrigerated transit...')
    return {'logistics_ready': True}

workflow = StateGraph(ProcurementState)
workflow.add_node('check_quality', validate_freshness)
workflow.add_node('cold_chain', manage_cold_chain)
workflow.set_entry_point('check_quality')
workflow.add_edge('check_quality', 'cold_chain')
workflow.add_edge('cold_chain', END)
graph = workflow.compile()
