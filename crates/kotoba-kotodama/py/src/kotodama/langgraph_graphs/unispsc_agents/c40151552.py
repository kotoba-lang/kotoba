from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpProcurementState(TypedDict):
    requirements: dict
    validation_result: bool
    compliance_report: str

def validate_specs(state: PumpProcurementState):
    specs = state.get('requirements', {})
    is_valid = 'flow_rate_accuracy' in specs and 'wetted_materials_compatibility' in specs
    return {'validation_result': is_valid}

def generate_report(state: PumpProcurementState):
    return {'compliance_report': 'Technical validation complete' if state['validation_result'] else 'Missing critical specs'}

graph = StateGraph(PumpProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
