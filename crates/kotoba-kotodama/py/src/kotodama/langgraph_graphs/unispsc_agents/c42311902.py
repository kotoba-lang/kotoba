from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DrainageProcurementState(TypedDict):
    product_id: str
    spec_data: dict
    is_compliant: bool
    validation_log: List[str]

def validate_medical_specs(state: DrainageProcurementState):
    specs = state.get('spec_data', {})
    log = []
    compliant = True
    if 'ISO 13485' not in specs.get('certifications', []):
        log.append('Missing mandatory ISO 13485 certification')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def route_by_compliance(state: DrainageProcurementState):
    return 'compliant' if state['is_compliant'] else 'manual_review'

graph = StateGraph(DrainageProcurementState)
graph.add_node('validate', validate_medical_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'compliant': END, 'manual_review': END})
graph = graph.compile()
