from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    device_specs: dict
    validation_passed: bool

def validate_specs(state: ProcurementState):
    specs = state.get('device_specs', {})
    # Ensure wireless devices have Bluetooth 5.0+
    if specs.get('type') == 'wireless' and specs.get('bt_version', 0) < 5.0:
        return {'validation_passed': False}
    return {'validation_passed': True}

workflow = StateGraph(ProcurementState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
