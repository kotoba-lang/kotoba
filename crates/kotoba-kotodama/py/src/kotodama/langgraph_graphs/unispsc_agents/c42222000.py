from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    spec_sheet: dict
    validation_status: str
    compliance_report: str

def validate_medical_specs(state: PumpState):
    specs = state.get('spec_sheet', {})
    if 'ISO_13485' in specs and 'Accuracy_Tolerance_Range' in specs:
        return {'validation_status': 'COMPLIANT'}
    return {'validation_status': 'REJECTED'}

def generate_report(state: PumpState):
    return {'compliance_report': f'Device validation finished with status: {state['validation_status']}'}

graph = StateGraph(PumpState)
graph.add_node('validate', validate_medical_specs)
graph.add_node('report', generate_report)
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph.set_entry_point('validate')
graph = graph.compile()
