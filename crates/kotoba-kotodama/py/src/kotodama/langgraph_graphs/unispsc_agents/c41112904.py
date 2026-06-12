from typing import TypedDict
from langgraph.graph import StateGraph, END

class ControlDeviceState(TypedDict):
    spec_data: dict
    validation_passed: bool
    log: list

def validate_specs(state: ControlDeviceState):
    specs = state.get('spec_data', {})
    critical_fields = ['Input/Output Voltage Range', 'Communication Protocols']
    passed = all(field in specs for field in critical_fields)
    return {'validation_passed': passed, 'log': [f'Validation: {passed}']}

def export_control_check(state: ControlDeviceState):
    # Simulate dual-use export check logic
    return {'log': state['log'] + ['Export control check completed']}

graph = StateGraph(ControlDeviceState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', export_control_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
