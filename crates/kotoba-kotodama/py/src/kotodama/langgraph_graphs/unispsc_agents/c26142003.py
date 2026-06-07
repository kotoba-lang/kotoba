from typing import TypedDict
from langgraph.graph import StateGraph, END

class NIMProcessingState(TypedDict):
    model_number: str
    compliance_certified: bool
    export_license_required: bool
    validation_passed: bool

def validate_nim_specs(state: NIMProcessingState):
    is_valid = bool(state.get('model_number')) and state.get('compliance_certified', False)
    return {'validation_passed': is_valid}

def check_export_controls(state: NIMProcessingState):
    license_needed = True if state.get('radiation_sensor_present') else False
    return {'export_license_required': license_needed}

graph = StateGraph(NIMProcessingState)
graph.add_node('validate', validate_nim_specs)
graph.add_node('export', check_export_controls)
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph.set_entry_point('validate')
graph = graph.compile()
