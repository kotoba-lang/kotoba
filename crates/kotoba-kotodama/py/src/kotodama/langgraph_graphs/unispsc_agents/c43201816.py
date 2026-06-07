from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class UDOProcurementState(TypedDict):
    device_id: str
    spec_compliance: bool
    export_control_check: bool
    final_approval: bool

def validate_specs(state: UDOProcurementState):
    print(f'Validating specs for {state.get('device_id')}')
    return {'spec_compliance': True}

def check_export_controls(state: UDOProcurementState):
    print('Checking dual-use export regulations')
    return {'export_control_check': True}

graph = StateGraph(UDOProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
