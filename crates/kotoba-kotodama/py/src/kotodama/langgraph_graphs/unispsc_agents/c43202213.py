from langgraph.graph import StateGraph, END
from typing import TypedDict
class DriveState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
def validate_specs(state: DriveState):
    specs = state.get('spec_sheet', {})
    is_valid = all(k in specs for k in ['voltage', 'torque', 'interface'])
    print(f'Validating specs: {is_valid}')
    return {'validation_passed': is_valid}
def export_compliance_check(state: DriveState):
    print('Checking dual-use export control status...')
    return {'validation_passed': state['validation_passed']}
graph = StateGraph(DriveState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', export_compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
