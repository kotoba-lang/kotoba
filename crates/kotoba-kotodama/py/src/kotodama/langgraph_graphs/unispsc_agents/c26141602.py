from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_id: str
    compliance_docs: List[str]
    needs_export_review: bool

def validate_nuclear_specs(state: ProcurementState):
    print('Validating nuclear grade specifications...')
    return {'compliance_docs': ['ISO9001', 'Nuclear-QA-1'], 'needs_export_review': True}

def export_control_check(state: ProcurementState):
    if state['needs_export_review']:
        print('Triggering dual-use export control workflow...')
    return {'needs_export_review': False}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_nuclear_specs)
graph.add_node('export_check', export_control_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)

graph = graph.compile()
