from langgraph.graph import StateGraph, END
from typing import TypedDict
class PhElectrodeState(TypedDict):
    spec_sheet: dict
    validation_status: str
    approval: bool
def validate_sensor_specs(state: PhElectrodeState):
    specs = state.get('spec_sheet', {})
    if 'range' in specs and 'type' in specs:
        return {'validation_status': 'COMPLIANT'}
    return {'validation_status': 'MISSING_DATA'}
def approve_procurement(state: PhElectrodeState):
    return {'approval': state['validation_status'] == 'COMPLIANT'}
graph = StateGraph(PhElectrodeState)
graph.add_node('validate', validate_sensor_specs)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
