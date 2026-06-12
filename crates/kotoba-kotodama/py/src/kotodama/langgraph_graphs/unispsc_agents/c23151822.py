from typing import TypedDict, Annotated; from langgraph.graph import StateGraph, END; import operator

class LaserProcurementState(TypedDict):
    spec_data: dict
    validation_log: Annotated[list, operator.add]
    is_compliant: bool

def validate_safety_protocols(state: LaserProcurementState):
    specs = state.get('spec_data', {})
    compliant = specs.get('laser_class') in ['Class 1', 'Class 4']
    return {'validation_log': ['Safety protocols validated'], 'is_compliant': compliant}

def export_control_check(state: LaserProcurementState):
    is_controlled = state.get('spec_data', {}).get('max_w', 0) > 500
    return {'validation_log': [f'Dual-use control: {is_controlled}']}

graph = StateGraph(LaserProcurementState)
graph.add_node('safety_check', validate_safety_protocols)
graph.add_node('export_check', export_control_check)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
