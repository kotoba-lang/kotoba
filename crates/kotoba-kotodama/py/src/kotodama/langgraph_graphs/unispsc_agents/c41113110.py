from typing import TypedDict
from langgraph.graph import StateGraph, END

class GasAnalyzerState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: GasAnalyzerState):
    specs = state.get('spec_data', {})
    # Logic to verify calibration compliance
    passed = 'Calibration standard' in specs and specs['Calibration standard'] == 'ISO/IEC 17025'
    return {'validation_passed': passed}

def generate_compliance(state: GasAnalyzerState):
    status = 'Pass' if state['validation_passed'] else 'Fail'
    return {'compliance_report': f'Compliance status: {status}. Export control check required.'}

graph = StateGraph(GasAnalyzerState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', generate_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
