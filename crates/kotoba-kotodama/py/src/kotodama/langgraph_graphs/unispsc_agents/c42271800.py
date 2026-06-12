from typing import TypedDict
from langgraph.graph import StateGraph, END

class RespiratoryOrder(TypedDict):
    device_type: str
    compliance_docs: list
    is_validated: bool

def validate_compliance(state: RespiratoryOrder):
    docs = state.get('compliance_docs', [])
    is_valid = 'ISO_13485' in docs and 'Medical_Device_License' in docs
    return {'is_validated': is_valid}

def process_order(state: RespiratoryOrder):
    if state['is_validated']:
        print('Processing high-grade medical aerosol equipment')
    return {}

graph = StateGraph(RespiratoryOrder)
graph.add_node('validate', validate_compliance)
graph.add_node('process', process_order)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
